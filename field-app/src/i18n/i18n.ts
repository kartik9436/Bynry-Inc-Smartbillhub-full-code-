/**
 * The i18n layer (T-14): one i18next instance, runtime language switching,
 * English as the fallback, and never a raw key on screen.
 *
 * Switching is `setLanguage(code)`: the catalogue is loaded if it has not
 * been, i18next changes language, and every component reading words through
 * `useTranslation` re-renders — nothing restarts and nothing is lost.
 *
 * ⚠ **A MISSING KEY NEVER PRINTS ITSELF.** i18next's default for a key it
 * cannot find in the language or in English is to return the key, so a
 * technician would read `field.screen.ff27` on a button. Here a key missing in
 * the chosen language falls back to English; a key missing in English too
 * renders as nothing and is reported through `onMissingKey` — and
 * `tests/i18n/keys.test.ts` fails any `field.*` key used in `src/` that
 * `field-keys.en.json` does not hold, so that second case is caught before it
 * ships rather than on a handset.
 */
import i18next, { type i18n as I18n } from 'i18next';
import { initReactI18next } from 'react-i18next';

import { type CatalogueSource, sharedCatalogues } from './catalogues';
import { FALLBACK_LANGUAGE, type LanguageCode, isLanguageCode } from './languages';

export const NAMESPACE = 'translation';

export interface FieldI18nOptions {
  language: LanguageCode;
  source?: CatalogueSource;
  onMissingKey?: (language: string, key: string) => void;
}

export interface FieldI18n {
  i18n: I18n;
  setLanguage(code: LanguageCode): Promise<void>;
  language(): LanguageCode;
}

export function createFieldI18n(options: FieldI18nOptions): FieldI18n {
  const source = options.source ?? sharedCatalogues;
  const instance = i18next.createInstance();
  const loaded = new Set<LanguageCode>();

  function ensure(code: LanguageCode): void {
    if (loaded.has(code)) return;
    instance.addResourceBundle(code, NAMESPACE, source(code), true, true);
    loaded.add(code);
  }

  instance.use(initReactI18next).init({
    lng: options.language,
    fallbackLng: FALLBACK_LANGUAGE,
    ns: [NAMESPACE],
    defaultNS: NAMESPACE,
    resources: {},
    // Catalogues are flat maps: "field.nav.tab.home" is ONE key, not a path.
    keySeparator: false,
    nsSeparator: false,
    interpolation: { escapeValue: false },
    returnNull: false,
    returnEmptyString: false,
    initAsync: false,
    saveMissing: true,
    missingKeyHandler: (lngs, _ns, key) => {
      options.onMissingKey?.(Array.isArray(lngs) ? lngs.join(',') : String(lngs), key);
    },
    parseMissingKeyHandler: () => '',
    react: { useSuspense: false, bindI18n: 'languageChanged loaded' },
  });
  ensure(FALLBACK_LANGUAGE);
  ensure(options.language);

  return {
    i18n: instance,
    async setLanguage(code) {
      if (!isLanguageCode(code)) return;
      ensure(code);
      await instance.changeLanguage(code);
    },
    language() {
      const current = instance.language;
      return isLanguageCode(current) ? current : FALLBACK_LANGUAGE;
    },
  };
}
