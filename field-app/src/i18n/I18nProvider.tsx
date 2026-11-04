/**
 * The language, in React. `useLanguage().setLanguage('de')` switches every
 * screen at once, at run time, and remembers the choice on this handset.
 *
 * The choice is a per-handset preference, not per technician: the design's
 * Settings (FF-51) has one Language row, and on a shared van tablet the
 * language is the van's until somebody changes it.
 */
import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from 'react';
import { I18nextProvider } from 'react-i18next';

import { type KeyValueStore } from '../security/prefs';
import { type FieldI18n } from './i18n';
import { LANGUAGES, type LanguageCode, isLanguageCode } from './languages';

export const PREF_LANGUAGE = 'handset.i18n.language';

/** The saved choice, if it is still one of the eleven. */
export function savedLanguage(prefs: KeyValueStore): LanguageCode | null {
  const saved = prefs.getString(PREF_LANGUAGE);
  return saved && isLanguageCode(saved) ? saved : null;
}

interface LanguageContextValue {
  language: LanguageCode;
  setLanguage(code: LanguageCode): Promise<void>;
  languages: typeof LANGUAGES;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function I18nProvider({
  fieldI18n,
  prefs,
  children,
}: {
  fieldI18n: FieldI18n;
  prefs?: KeyValueStore;
  children: ReactNode;
}) {
  const [language, setLanguageState] = useState<LanguageCode>(fieldI18n.language());

  const setLanguage = useCallback(
    async (code: LanguageCode) => {
      await fieldI18n.setLanguage(code);
      prefs?.set(PREF_LANGUAGE, code);
      setLanguageState(fieldI18n.language());
    },
    [fieldI18n, prefs],
  );

  const value = useMemo(() => ({ language, setLanguage, languages: LANGUAGES }), [language, setLanguage]);

  return (
    <I18nextProvider i18n={fieldI18n.i18n}>
      <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
    </I18nextProvider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useLanguage outside I18nProvider');
  return ctx;
}
