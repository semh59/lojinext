import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import en from "./locales/en.json";
import tr from "./locales/tr.json";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      tr: { translation: tr },
    },
    // No hardcoded `lng` — it would win over LanguageDetector every time,
    // which is why a saved language choice never survived a page reload.
    fallbackLng: "tr",
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
    },
  });

// Chromium applies Turkish case-folding (dotted İ) to CSS
// text-transform:uppercase whenever <html lang="tr">, even when the
// visible text is English — keep the attribute in sync with the active
// language so English uppercase labels don't render with stray İ/ı.
const syncDocumentLang = (lng: string) => {
  document.documentElement.lang = lng;
};
syncDocumentLang(i18n.resolvedLanguage ?? i18n.language);
i18n.on("languageChanged", syncDocumentLang);

export default i18n;
