import React from "react";
import { useTranslation } from "react-i18next";
import { Languages } from "lucide-react";

const LanguageSwitcher: React.FC = () => {
  const { i18n } = useTranslation();
  const isEnglishActive = (i18n.language || "tr").startsWith("en");
  // Button shows the language you'll SWITCH TO, not the active one — press
  // "EN" to go English (button then flips to "TR" to go back), press "TR"
  // to go Turkish (button flips to "EN"). Previously showed the active
  // language instead, which read backwards to users.
  const targetLabel = isEnglishActive ? "TR" : "EN";

  const toggleLanguage = () => {
    i18n.changeLanguage(isEnglishActive ? "tr" : "en");
  };

  // Icon-first button styled to match the adjacent theme toggle so the two
  // form a consistent pair (was a bordered "Globe + EN" pill that clashed).
  return (
    <button
      onClick={toggleLanguage}
      className="flex items-center gap-1.5 rounded-xl p-2.5 text-secondary transition-colors hover:bg-elevated hover:text-primary"
      title={isEnglishActive ? "Türkçe'ye geç" : "Switch to English"}
      aria-label={isEnglishActive ? "Türkçe'ye geç" : "Switch to English"}
    >
      <Languages size={18} />
      <span className="text-[11px] font-bold uppercase tracking-wider">
        {targetLabel}
      </span>
    </button>
  );
};

export default LanguageSwitcher;
