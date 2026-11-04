/**
 * Every `field.*` key the code uses exists in English — the half of "never a
 * raw key" that has to be caught BEFORE a handset shows it.
 *
 * The scan reads every `.ts`/`.tsx` file under `src/` for string literals
 * starting `field.` (a `t('field.…')` call, a `labelKey`, a `titleKey`), and
 * adds the keys built at run time from a template, listed by hand below with
 * the file that builds them. It prints how many files it read, so a scan that
 * silently read nothing cannot pass (law 7).
 */
import { readdirSync, readFileSync, statSync } from 'fs';
import { join } from 'path';

// The shell's keys AND every screen wave's `keys/<wave>.en.json` — the same
// merge the app ships (`catalogues.ts`), so a wave's key is not "missing".
import { FIELD_KEYS_EN as fieldKeys } from '../../src/i18n/catalogues';
import { SCREEN_IDS, titleKeyOf } from '../../src/navigation/screens';

const SRC = join(__dirname, '../../src');

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path);
    return /\.(ts|tsx)$/.test(name) ? [path] : [];
  });
}

/** Keys assembled from a template, with the file that assembles them. */
const BUILT_AT_RUN_TIME = [
  // navigation/screens.ts — titleKeyOf(id), one per screen.
  ...SCREEN_IDS.map(titleKeyOf),
  // navigation/ShellStatus.tsx, navigation/MenuContent.tsx
  'field.status.connection.online',
  'field.status.connection.offline',
  'field.status.connection.unknown',
  'field.availability.available',
  'field.availability.onBreak',
  'field.availability.offDuty',
];

test('every field.* key used in src/ exists in the English keys (shell + every wave file)', () => {
  const sources = files(SRC);
  expect(sources.length).toBeGreaterThan(25);
  const used = new Set<string>(BUILT_AT_RUN_TIME);
  for (const file of sources) {
    for (const m of readFileSync(file, 'utf8').matchAll(/['"`](field\.[A-Za-z0-9_.]+)['"`]/g)) {
      // A key prefix used to build others ends in a dot; the full keys are listed above.
      if (m[1] && !m[1].endsWith('.')) used.add(m[1]);
    }
  }
  const defined = new Set(Object.keys(fieldKeys));
  const missing = [...used].filter((k) => !defined.has(k));
  expect(missing).toEqual([]);
});

test('every English key is a field.* key with words in it', () => {
  for (const [key, value] of Object.entries(fieldKeys)) {
    expect(key.startsWith('field.')).toBe(true);
    expect(String(value).trim()).not.toBe('');
  }
});
