import { useSyncExternalStore } from 'react';
import { DEFAULT_LOCALE, LOCALE_STORAGE_KEY, SUPPORTED_LOCALES, type Locale } from './config';
import en from './translations/en.json';
import es from './translations/es.json';

const translations: Record<Locale, Record<string, Record<string, string>>> = { es, en };

function detectLocale(): Locale {
  if (typeof window === 'undefined') return DEFAULT_LOCALE;
  const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  if (stored && (SUPPORTED_LOCALES as string[]).includes(stored)) return stored as Locale;
  // POC: Spanish by default (es-MX). English via setLocale() for dev/tests only.
  return DEFAULT_LOCALE;
}

let currentLocale = detectLocale();
const listeners = new Set<() => void>();

if (typeof window !== 'undefined') {
  document.documentElement.lang = currentLocale;
}

export function getLocale(): Locale {
  return currentLocale;
}

export function setLocale(locale: Locale): void {
  currentLocale = locale;
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    document.documentElement.lang = locale;
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * Get a translated string by dot-notation key.
 * Falls back to the key itself when missing.
 */
export function t(
  key: string | null | undefined,
  params?: Record<string, string | number>,
  locale: Locale = currentLocale,
): string {
  if (typeof key !== 'string' || key.length === 0) return '';
  const [namespace, ...rest] = key.split('.');
  const k = rest.join('.');
  let result = translations[locale]?.[namespace]?.[k] ?? key;
  if (params) {
    for (const [pk, pv] of Object.entries(params)) {
      result = result.replace(`{{${pk}}}`, String(pv));
    }
  }
  return result;
}

/** React hook: re-renders components when the locale changes. */
export function useTranslation() {
  const locale = useSyncExternalStore(subscribe, getLocale, () => DEFAULT_LOCALE);
  return {
    locale,
    setLocale,
    t: (key: string, params?: Record<string, string | number>) => t(key, params, locale),
  };
}
