import { useTranslation } from "react-i18next";

export function useLocale(): string {
  const { i18n } = useTranslation();
  return (i18n.language ?? "tr").startsWith("en") ? "en-US" : "tr-TR";
}
