import React from "react";
import { motion } from "framer-motion";
import { Check, Brain } from "lucide-react";

const FIELD_MAP = {
  current_level: { ar: "مستواك", en: "Level", map: { beginner: ["مبتدئ", "Beginner"], intermediate: ["متوسط", "Intermediate"], advanced: ["متقدم", "Advanced"] } },
  weekly_hours: { ar: "وقتك في الأسبوع", en: "Weekly hours" },
  learning_style: { ar: "أسلوبك", en: "Style", map: { visual: ["بصري", "Visual"], video: ["فيديو", "Video"], reading: ["قراءة", "Reading"], hands_on: ["تطبيقي", "Hands-on"], mixed: ["مختلط", "Mixed"] } },
  preferred_language: { ar: "لغة المحتوى", en: "Content language", map: { ar: ["عربي", "Arabic"], en: ["إنجليزي", "English"], mixed: ["مختلط", "Mixed"] } },
  depth: { ar: "العمق", en: "Depth", map: { overview: ["نظرة عامة", "Overview"], balanced: ["متوازن", "Balanced"], deep: ["تعمّق", "Deep"] } },
  career_intent: { ar: "هدفك المهني", en: "Career intent" },
  motivation: { ar: "اللي بيحركك", en: "Motivation" },
  background: { ar: "خلفيتك", en: "Background" },
  education: { ar: "تعليمك", en: "Education" },
  experience: { ar: "خبرتك", en: "Experience" },
  obstacles: { ar: "التحديات", en: "Challenges" },
  video_preference: {
    ar: "المصادر التعليمية",
    en: "Learning Resources",
    map: {
      free: ["مصادر مجانية بالكامل من YouTube", "Exclusively Free from YouTube"],
      mixed: ["مصادر مجانية بالكامل من YouTube", "Exclusively Free from YouTube"],
      youtube: ["مصادر مجانية بالكامل من YouTube", "Exclusively Free from YouTube"],
    }
  },
  known_skills: { ar: "مهاراتك الحالية", en: "Current skills" },
  target_skills: { ar: "مهارات مستهدفة", en: "Target skills" },
  strengths: { ar: "نقاط قوتك", en: "Strengths" },
  goal: { ar: "هدفك", en: "Goal" },
  available_days: { ar: "أيامك", en: "Days" }
};

export default function DnaSummary({ profile, isAr, Arrow, onConfirm }) {
  const chips = Object.entries(FIELD_MAP)
    .map(([key, config]) => {
      const raw = profile?.[key];
      if (!raw || (Array.isArray(raw) && raw.length === 0)) return null;
      let value;
      if (Array.isArray(raw)) {
        value = raw.map((d) => {
          const dayMap = { monday: isAr ? "الاثنين" : "Mon", tuesday: isAr ? "الثلاثاء" : "Tue", wednesday: isAr ? "الأربعاء" : "Wed", thursday: isAr ? "الخميس" : "Thu", friday: isAr ? "الجمعة" : "Fri", saturday: isAr ? "السبت" : "Sat", sunday: isAr ? "الأحد" : "Sun" };
          return dayMap[d] || d;
        }).join("، ");
      } else if (config.map) {
        value = config.map[raw] ? config.map[raw][isAr ? 0 : 1] : raw;
      } else if (key === "weekly_hours") {
        value = `${raw} ${isAr ? "ساعات" : "hrs"}`;
      } else {
        value = String(raw);
      }
      return { label: isAr ? config.ar : config.en, value };
    })
    .filter(Boolean);

  return (
    <div className="animate-fade-up">
      <div className="text-center mb-6">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-zeus-gold/15 border border-zeus-gold/30 flex items-center justify-center mb-3">
          <Brain className="text-zeus-gold" style={{ width: 26, height: 26 }} />
        </div>
        <h2 className="font-heading font-extrabold text-2xl sm:text-3xl">{isAr ? "ده الـ DNA بتاع تعلّمك" : "This is your Learning DNA"}</h2>
        <p className="text-muted-foreground mt-2 text-sm">
          {isAr ? "كل ده استنتجته من كلامنا — تقدر تعدّل أي حاجة بعدين من الإعدادات." : "I inferred all of this from our chat — you can adjust anything later in settings."}
        </p>
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }}
        className="flex flex-wrap gap-2 justify-center mb-6">
        {chips.map((c, i) => (
          <motion.span key={c.label} initial={{ opacity: 0, scale: 0.85 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.15 + i * 0.06 }}
            className="px-3 py-1.5 rounded-full bg-secondary/40 border border-border/60 text-xs">
            <span className="text-muted-foreground">{c.label}:</span> <span className="font-medium">{c.value}</span>
          </motion.span>
        ))}
        {chips.length === 0 && (
          <p className="text-muted-foreground text-sm">
            {isAr ? "لسه مفيش بيانات كفاية — ارجع كمل الشات عشان أتعرف عليك أكتر." : "Not enough data yet — go back and chat more so I can learn about you."}
          </p>
        )}
      </motion.div>

      <div className="text-center mt-6">
        <button onClick={() => onConfirm({})}
          className="inline-flex items-center gap-2 px-7 py-3.5 rounded-full bg-zeus-gold text-zeus-midnight font-semibold hover:bg-zeus-brightgold transition shadow-gold">
          <Check style={{ width: 18, height: 18 }} /> {isAr ? "كمّل" : "Continue"} <Arrow style={{ width: 18, height: 18 }} />
        </button>
      </div>
    </div>
  );
}