import { useTranslation } from "react-i18next";

export function useLocale(): string {
  const { i18n } = useTranslation();
  return i18n.language.startsWith("en") ? "en-US" : "tr-TR";
}
