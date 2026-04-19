import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { activateLocale, isSupportedLocale, type SupportedLocale } from '../i18n/init';
import { detectBrowserLocale } from '../lib/locale-detect';

const STORAGE_KEY = 'trainsight-locale';

function readStoredLocale(): SupportedLocale | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return isSupportedLocale(stored) ? stored : null;
  } catch {
    return null;
  }
}

function writeStoredLocale(locale: SupportedLocale | null) {
  try {
    if (locale === null) localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // localStorage unavailable
  }
}

interface LocaleContextValue {
  locale: SupportedLocale;
  setLocale: (locale: SupportedLocale) => Promise<void>;
}

const LocaleContext = createContext<LocaleContextValue>({
  locale: 'en',
  setLocale: async () => {},
});

function initialLocale(): SupportedLocale {
  return readStoredLocale() ?? detectBrowserLocale();
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<SupportedLocale>(initialLocale);

  // Apply locale on mount and whenever it changes: update Lingui catalog +
  // reflect on <html lang> for a11y and CSS locale-aware selectors.
  useEffect(() => {
    activateLocale(locale).catch(() => {
      // Missing catalog: Lingui falls back to source IDs (English); safe.
    });
    if (typeof document !== 'undefined') {
      document.documentElement.lang = locale;
    }
  }, [locale]);

  const setLocale = useCallback(async (next: SupportedLocale) => {
    await activateLocale(next);
    writeStoredLocale(next);
    setLocaleState(next);
  }, []);

  const value = useMemo(() => ({ locale, setLocale }), [locale, setLocale]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  return useContext(LocaleContext);
}
