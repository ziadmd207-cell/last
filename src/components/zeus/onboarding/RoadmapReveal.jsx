import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Map, Rocket, Sparkles, Target, Clock, ListChecks, AlertCircle, RotateCcw } from "lucide-react";
import { ZEUS_IMAGES, withImageFallback } from "@/lib/zeus-images";

export default function RoadmapReveal({ preview, typing, building, onBuild, onRetry, error, isAr, companionName }) {
  const nodes = preview?.nodes || [];
  const phases = [...new Set(nodes.map((n) => n.phase))].sort((a, b) => a - b);
  const skills = [...new Set(nodes.flatMap((n) => n.skills || []))].slice(0, 10);
  const totalHours = nodes.reduce((sum, n) => sum + (n.estimated_hours || 0), 0);
  const totalProjects = nodes.reduce((sum, n) => sum + (n.projects || []).length, 0);
  const [stage, setStage] = useState(0);

  useEffect(() => {
    if (!preview) return;
    setStage(1);
    const t1 = setTimeout(() => setStage(2), 2200);
    const t2 = setTimeout(() => setStage(3), 2200 + phases.length * 500 + 800);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [preview]);

  if (typing || !preview) {
    // A failed generation resolves preview to null + error flag: show the
    // retry state instead of hanging on the spinner forever.
    if (error && !typing) {
      return (
        <div className="text-center animate-fade-up">
          <div className="zeus-glass p-8">
            <AlertCircle className="text-zeus-gold mx-auto mb-3" style={{ width: 30, height: 30 }} />
            <h3 className="font-heading font-bold text-lg mb-1">{isAr ? "تعثر توليد الخريطة" : "Roadmap generation stumbled"}</h3>
            <p className="text-muted-foreground text-sm mb-5">{isAr ? "تقديراتك محفوظة — دوس إعادة المحاولة" : "Your inputs are saved — hit retry"}</p>
            <button onClick={onRetry} className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-zeus-gold text-zeus-midnight font-semibold hover:bg-zeus-brightgold transition shadow-gold text-sm">
              <RotateCcw style={{ width: 16, height: 16 }} /> {isAr ? "إعادة المحاولة" : "Retry"}
            </button>
          </div>
        </div>
      );
    }
    return (
      <div className="text-center animate-fade-up">
        <div className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-zeus-gold to-zeus-brightgold flex items-center justify-center mb-6 shadow-gold animate-float">
          <Map className="text-zeus-midnight" style={{ width: 36, height: 36 }} />
        </div>
        <div className="flex flex-col items-center gap-3 py-6">
          <Loader2 className="text-zeus-gold animate-spin" style={{ width: 30, height: 30 }} />
          <p className="text-muted-foreground text-sm">
            {isAr ? "بحلّل مهاراتك وبصمّم رحلتك خطوة بخطوة..." : "Analyzing your skills and designing your journey step by step..."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-up" dir={isAr ? "rtl" : "ltr"}>
      {/* Companion narration */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-start gap-3 mb-5">
        <div className="shrink-0 w-10 h-10 rounded-full overflow-hidden border border-zeus-gold/40">
          <img src={ZEUS_IMAGES.avatar} alt="Zeus" className="w-full h-full object-cover object-top" onError={withImageFallback} />
        </div>
        <div className="zeus-glass p-4 flex-1">
          <p className="text-sm leading-relaxed">
            {isAr
              ? "بناءً على كلامنا، دي المهارات اللي شايفها الأنسب ليك والأكتر طلبًا في السوق — وقسمتهالك مراحل، كل واحدة بتبني على اللي قبلها."
              : "Based on our talk, these are the skills I see as the best fit for you and most in demand — split into phases, each building on the last."}
          </p>
        </div>
      </motion.div>

      {/* Stats */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="grid grid-cols-4 gap-2 mb-5">
        {[
          { icon: Map, value: phases.length, label: isAr ? "مراحل" : "Phases" },
          { icon: Clock, value: totalHours, label: isAr ? "ساعة" : "Hours" },
          { icon: ListChecks, value: nodes.length, label: isAr ? "دروس" : "Lessons" },
          { icon: Rocket, value: totalProjects, label: isAr ? "مشاريع" : "Projects" }
        ].map((s, i) => {
          const Icon = s.icon;
          return (
            <div key={i} className="zeus-glass p-3 text-center">
              <Icon className="text-zeus-gold mx-auto mb-1" style={{ width: 16, height: 16 }} />
              <div className="font-heading font-bold text-lg">{s.value}</div>
              <div className="text-[10px] text-muted-foreground">{s.label}</div>
            </div>
          );
        })}
      </motion.div>

      {/* Skills reveal */}
      <AnimatePresence>
        {stage >= 1 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-5">
            <div className="text-xs font-semibold uppercase tracking-wide text-zeus-brightgold flex items-center gap-1.5 mb-2.5">
              <Sparkles style={{ width: 13, height: 13 }} /> {isAr ? "هنبني المهارات دي مع بعض" : "We'll build these skills together"}
            </div>
            <div className="flex flex-wrap gap-2">
              {skills.map((s, i) => (
                <motion.span key={s} initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.1, type: "spring", stiffness: 300, damping: 20 }}
                  className="px-3 py-1.5 rounded-full bg-zeus-gold/10 border border-zeus-gold/30 text-zeus-brightgold text-xs font-medium">
                  {s}
                </motion.span>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Phases reveal */}
      <AnimatePresence>
        {stage >= 2 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-2.5 max-h-[34vh] overflow-y-auto pe-1">
            {phases.map((p, i) => {
              const phaseNodes = nodes.filter((n) => n.phase === p);
              const phaseProjects = phaseNodes.flatMap((n) => n.projects || []);
              return (
                <motion.div key={p} initial={{ opacity: 0, x: isAr ? 20 : -20 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.4, duration: 0.4 }}
                  className="zeus-glass p-3.5 flex items-start gap-3">
                  <div className="shrink-0 w-8 h-8 rounded-full bg-zeus-gold text-zeus-midnight flex items-center justify-center text-sm font-bold">{p}</div>
                  <div className="min-w-0 flex-1">
                    <div className="text-zeus-brightgold text-xs font-semibold mb-1">{isAr ? `المرحلة ${p}` : `Phase ${p}`}</div>
                    <div className="flex flex-wrap gap-1.5 mb-1.5">
                      {phaseNodes.map((n) => (
                        <span key={n.id} className="px-2.5 py-1 rounded-full bg-secondary/40 text-xs">{n.title}</span>
                      ))}
                    </div>
                    {phaseProjects.length > 0 && (
                      <div className="text-[11px] text-muted-foreground flex items-center gap-1">
                        <Rocket style={{ width: 11, height: 11 }} className="text-zeus-gold" />
                        {isAr ? "مشاريع: " : "Projects: "}{phaseProjects.join("، ")}
                      </div>
                    )}
                    {i < phases.length - 1 && (
                      <div className="text-[11px] text-zeus-gold/60 mt-1">{isAr ? "↓ اختبار قبل الانتقال للمرحلة التالية" : "↓ Assessment before next phase"}</div>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>

      {/* CTA */}
      <AnimatePresence>
        {stage >= 3 && (
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="text-center mt-6">
            <p className="text-sm text-muted-foreground mb-3">
              {isAr ? "جاهز؟ هعملك خريطة تفاعلية — كل محطة فيها مهام ومصادر ومشاريع واختبارات." : "Ready? I'll build your interactive map — every stop has tasks, resources, projects, and assessments."}
            </p>
            <button onClick={onBuild} disabled={building}
              className="inline-flex items-center gap-2 px-8 py-4 rounded-full bg-zeus-gold text-zeus-midnight font-semibold hover:bg-zeus-brightgold transition shadow-gold disabled:opacity-50">
              {building
                ? <><Loader2 className="animate-spin" style={{ width: 18, height: 18 }} /> {isAr ? "ببني رحلتك..." : "Building your journey..."}</>
                : <><Rocket style={{ width: 18, height: 18 }} /> {isAr ? "يلا نبدأ الرحلة" : "Start the journey"}</>}
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}