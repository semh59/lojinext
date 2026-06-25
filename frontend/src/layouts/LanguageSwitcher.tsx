import React from "react";
import { useTranslation } from "react-i18next";
import { Languages } from "lucide-react";

const LanguageSwitcher: React.FC = () => {
  const { i18n } = useTranslation();
  const current = (i18n.language || "tr").startsWith("en") ? "EN" : "TR";

  const toggleLanguage = () => {
    i18n.changeLanguage(current === "EN" ? "tr" : "en");
  };

  // Icon-first button styled to match the adjacent theme toggle so the two
  // form a consistent pair (was a bordered "Globe + EN" pill that clashed).
  return (
    <button
      onClick={toggleLanguage}
      className="flex items-center gap-1.5 rounded-xl p-2.5 text-secondary transition-colors hover:bg-elevated hover:text-primary"
      title={current === "EN" ? "Türkçe'ye geç" : "Switch to English"}
      aria-label={current === "EN" ? "Türkçe'ye geç" : "Switch to English"}
    >
      <Languages size={18} />
      <span className="text-[11px] font-bold uppercase tracking-wider">
        {current}
      </span>
    </button>
  );
};

export default LanguageSwitcher;
