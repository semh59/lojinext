import React from "react";
import { useTranslation } from "react-i18next";
import { Globe } from "lucide-react";

const LanguageSwitcher: React.FC = () => {
  const { i18n } = useTranslation();

  const toggleLanguage = () => {
    const nextLng = i18n.language === "en" ? "tr" : "en";
    i18n.changeLanguage(nextLng);
  };

  return (
    <button
      onClick={toggleLanguage}
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-elevated hover:bg-accent-soft text-secondary hover:text-accent transition-all duration-200 border border-border"
      title="Switch Language"
    >
      <Globe size={16} />
      <span className="text-xs font-bold uppercase tracking-wider">
        {i18n.language === "en" ? "TR" : "EN"}
      </span>
    </button>
  );
};

export default LanguageSwitcher;
