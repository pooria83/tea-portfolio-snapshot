import i18next from 'i18next';
import {initReactI18next} from 'react-i18next';
import {I18nManager, NativeModules, Platform} from 'react-native';
import arAuth from './locales/ar/auth.json';
import arChat from './locales/ar/chat.json';
import arCommon from './locales/ar/common.json';
import arError from './locales/ar/error.json';
import arNav from './locales/ar/nav.json';
import arPermissions from './locales/ar/permissions.json';
import arProfile from './locales/ar/profile.json';
import enAuth from './locales/en/auth.json';
import enChat from './locales/en/chat.json';
import enCommon from './locales/en/common.json';
import enError from './locales/en/error.json';
import enNav from './locales/en/nav.json';
import enPermissions from './locales/en/permissions.json';
import enProfile from './locales/en/profile.json';
import faAuth from './locales/fa/auth.json';
import faChat from './locales/fa/chat.json';
import faCommon from './locales/fa/common.json';
import faError from './locales/fa/error.json';
import faNav from './locales/fa/nav.json';
import faPermissions from './locales/fa/permissions.json';
import faProfile from './locales/fa/profile.json';

export const SUPPORTED_LANGUAGES = ['ar', 'en', 'fa'] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

const isRtlLanguage = (lang: string): boolean => lang === 'ar' || lang === 'fa';

export const isSupportedLanguage = (
  lang: string | null | undefined,
): lang is SupportedLanguage =>
  lang != null && (SUPPORTED_LANGUAGES as readonly string[]).includes(lang);

const getDeviceLocale = (): SupportedLanguage => {
  const settingsManager = NativeModules.SettingsManager as
    {settings?: {AppleLocale?: string; AppleLanguages?: string[]}} | undefined;
  const i18nManager = NativeModules.I18nManager as
    {localeIdentifier?: string} | undefined;
  const locale =
    Platform.OS === 'ios'
      ? (settingsManager?.settings?.AppleLocale ??
        settingsManager?.settings?.AppleLanguages?.[0])
      : i18nManager?.localeIdentifier;
  const lang = locale?.split('_')[0] ?? 'en';
  return isSupportedLanguage(lang) ? lang : 'en';
};

const deviceLocale = getDeviceLocale();
// On Android the RTL flag is applied natively in MainActivity before the root
// view is laid out (using the persisted language or the device locale), so we
// only apply it here on other platforms.
if (Platform.OS !== 'android') {
  I18nManager.forceRTL(isRtlLanguage(deviceLocale));
}
I18nManager.allowRTL(true);

const resources = {
  ar: {
    auth: arAuth,
    chat: arChat,
    common: arCommon,
    error: arError,
    nav: arNav,
    permissions: arPermissions,
    profile: arProfile,
  },
  en: {
    auth: enAuth,
    chat: enChat,
    common: enCommon,
    error: enError,
    nav: enNav,
    permissions: enPermissions,
    profile: enProfile,
  },
  fa: {
    auth: faAuth,
    chat: faChat,
    common: faCommon,
    error: faError,
    nav: faNav,
    permissions: faPermissions,
    profile: faProfile,
  },
} as const;

void i18next.use(initReactI18next).init({
  resources,
  lng: deviceLocale,
  fallbackLng: 'en',
  ns: ['auth', 'chat', 'common', 'error', 'nav', 'permissions', 'profile'],
  defaultNS: 'common',
  interpolation: {
    escapeValue: false,
  },
});

/**
 * Switches the interface language immediately. On Android, the RTL layout
 * direction takes effect on the next app launch (MainActivity applies it
 * before the first frame from the language persisted here).
 */
export const setAppLanguage = async (
  lang: SupportedLanguage,
): Promise<void> => {
  await i18next.changeLanguage(lang);
  I18nManager.forceRTL(isRtlLanguage(lang));
  I18nManager.allowRTL(true);
  if (Platform.OS === 'android') {
    const languagePrefs = NativeModules.LanguagePreferences as
      {setLanguage: (lang: string) => void} | undefined;
    if (languagePrefs != null) {
      languagePrefs.setLanguage(lang);
    }
  }
};

export default i18next;
