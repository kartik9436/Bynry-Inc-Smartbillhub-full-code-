/**
 * T-14 — runtime language switching against the eleven shared catalogues,
 * English as the fallback, and never a raw key on screen.
 *
 * Red first (law 7): with `parseMissingKeyHandler` taken out of
 * `src/i18n/i18n.ts`, the fallback test failed — i18next printed
 * `field.not.a.key.anywhere` on screen, which is exactly what a technician
 * would have read on a button.
 */
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import { useTranslation } from 'react-i18next';
import { Pressable, Text } from 'react-native';

import { FIELD_KEYS_EN, fieldSlice, sharedCatalogues } from '../../src/i18n/catalogues';
import { createFieldI18n } from '../../src/i18n/i18n';
import { I18nProvider, PREF_LANGUAGE, savedLanguage, useLanguage } from '../../src/i18n/I18nProvider';
import { LANGUAGES, matchLanguage } from '../../src/i18n/languages';
import { MemoryKeyValueStore } from '../../src/security/prefs';

const SOURCE = {
  en: { 'field.nav.tab.home': 'Home', 'field.nav.tab.jobs': 'Jobs', 'field.only.english': 'Only in English' },
  de: { 'field.nav.tab.home': 'Start', 'field.nav.tab.jobs': 'Aufträge' },
} as Record<string, Record<string, string>>;
const source = (code: string) => SOURCE[code] ?? {};

function Words() {
  const { t } = useTranslation();
  const { setLanguage } = useLanguage();
  return (
    <>
      <Text testID="home">{t('field.nav.tab.home')}</Text>
      <Text testID="english-only">{t('field.only.english')}</Text>
      <Text testID="nowhere">{t('field.not.a.key.anywhere')}</Text>
      <Pressable testID="to-de" onPress={() => setLanguage('de')} />
      <Pressable testID="to-en" onPress={() => setLanguage('en')} />
    </>
  );
}

describe('switching language at run time', () => {
  test('re-renders every word in the new language, and back, and remembers the choice', async () => {
    const prefs = new MemoryKeyValueStore();
    const fieldI18n = createFieldI18n({ language: 'en', source });
    render(
      <I18nProvider fieldI18n={fieldI18n} prefs={prefs}>
        <Words />
      </I18nProvider>,
    );
    expect(screen.getByTestId('home')).toHaveTextContent('Home');
    await act(async () => {
      fireEvent.press(screen.getByTestId('to-de'));
    });
    expect(screen.getByTestId('home')).toHaveTextContent('Start');
    expect(savedLanguage(prefs)).toBe('de');
    expect(prefs.getString(PREF_LANGUAGE)).toBe('de');
    await act(async () => {
      fireEvent.press(screen.getByTestId('to-en'));
    });
    expect(screen.getByTestId('home')).toHaveTextContent('Home');
  });

  test('a key missing in the language falls back to English; missing everywhere prints nothing, never the key', async () => {
    const missing: string[] = [];
    const fieldI18n = createFieldI18n({ language: 'de', source, onMissingKey: (_l, k) => missing.push(k) });
    render(
      <I18nProvider fieldI18n={fieldI18n}>
        <Words />
      </I18nProvider>,
    );
    expect(screen.getByTestId('home')).toHaveTextContent('Start');
    expect(screen.getByTestId('english-only')).toHaveTextContent('Only in English');
    expect(screen.getByTestId('nowhere')).toHaveTextContent('');
    expect(screen.queryByText(/field\./)).toBeNull();
    expect(missing).toContain('field.not.a.key.anywhere');
  });

  test('an unsaved or unknown saved language is ignored', () => {
    const prefs = new MemoryKeyValueStore();
    expect(savedLanguage(prefs)).toBeNull();
    prefs.set(PREF_LANGUAGE, 'xx-YY');
    expect(savedLanguage(prefs)).toBeNull();
  });
});

describe('picking the handset’s language', () => {
  test.each([
    [['de-DE'], 'de'],
    [['es-MX'], 'es-MX'],
    [['es-AR'], 'es'],
    [['pt-PT'], 'pt-BR'],
    [['nl-NL', 'fr-CA'], 'fr-FR'],
    [['nl-NL'], 'en'],
    [[], 'en'],
  ])('%j → %s', (tags, expected) => {
    expect(matchLanguage(tags)).toBe(expected);
  });

  test('the eleven languages are the eleven catalogues, in the fan-in tool’s order', () => {
    expect(LANGUAGES.map((l) => l.code)).toEqual([
      'en', 'de', 'es', 'es-MX', 'fr-FR', 'hi', 'id-ID', 'it-IT', 'ja-JP', 'ko-KR', 'pt-BR',
    ]);
  });
});

describe('the shared catalogues', () => {
  test('only field.* keys are taken from a catalogue', () => {
    expect(fieldSlice({ 'field.a': 'A', 'billing.b': 'B', 'field.empty': ' ', 'field.n': 3 })).toEqual({ 'field.a': 'A' });
    expect(fieldSlice(null)).toEqual({});
  });

  test('all eleven shared catalogues load, and none leaks a web key into the field app', () => {
    for (const { code } of LANGUAGES) {
      const words = sharedCatalogues(code);
      // `field.*`, and the server's own refusal sentences `work.*` (DEF-FLD-10579).
      expect(Object.keys(words).filter((k) => !k.startsWith('field.') && !k.startsWith('work.'))).toEqual([]);
    }
    // English always carries the field app's own keys, fanned in or not.
    expect(sharedCatalogues('en')).toMatchObject(FIELD_KEYS_EN);
  }, 60_000);
});
