/**
 * The eleven languages the product ships, in the catalogue order of
 * `10-scripts/i18n_fanin.py` (`LANGS`) — the same eleven files the web app
 * reads from `07-frontend/src/i18n/locales/`.
 *
 * Each language is named in ITSELF on the picker, so a technician who cannot
 * read the current language can still find their own.
 */
export const LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'de', name: 'Deutsch' },
  { code: 'es', name: 'Español' },
  { code: 'es-MX', name: 'Español (México)' },
  { code: 'fr-FR', name: 'Français' },
  { code: 'hi', name: 'हिन्दी' },
  { code: 'id-ID', name: 'Bahasa Indonesia' },
  { code: 'it-IT', name: 'Italiano' },
  { code: 'ja-JP', name: '日本語' },
  { code: 'ko-KR', name: '한국어' },
  { code: 'pt-BR', name: 'Português (Brasil)' },
] as const;

export type LanguageCode = (typeof LANGUAGES)[number]['code'];

export const FALLBACK_LANGUAGE: LanguageCode = 'en';

export function isLanguageCode(code: string): code is LanguageCode {
  return LANGUAGES.some((l) => l.code === code);
}

/**
 * The best of the eleven for the handset's own preference list (most
 * preferred first, BCP-47 tags as `expo-localization` gives them): an exact
 * tag first, then the same language in any region, then English.
 */
export function matchLanguage(preferred: readonly string[]): LanguageCode {
  for (const tag of preferred) {
    const exact = LANGUAGES.find((l) => l.code.toLowerCase() === tag.toLowerCase());
    if (exact) return exact.code;
    const base = tag.split('-')[0]?.toLowerCase();
    const sameLanguage = LANGUAGES.find((l) => l.code.split('-')[0]?.toLowerCase() === base);
    if (sameLanguage) return sameLanguage.code;
  }
  return FALLBACK_LANGUAGE;
}
