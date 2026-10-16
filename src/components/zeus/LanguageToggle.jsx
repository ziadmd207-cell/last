import React from "react";
import { Languages } from "lucide-react";
import { useI18n } from "@/lib/i18n";

export default function LanguageToggle({ className = "" }) {
  const { lang, setLang, t } = useI18n();
  return (
    <button
      onClick={() => setLang(lang === "ar" ? "en" : "ar")}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border border-border/70 bg-card/50 hover:bg-secondary/60 hover:zeus-gold-border transition ${className}`}
    >
      <Languages className="w-3.5 h-3.5 text-zeus-gold" />
      {t("common.translate")}
    </button>
  );
}