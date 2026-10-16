import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Check, Sparkles, Zap, Shield, ArrowRight, ArrowLeft,
  Upload, Loader2, CheckCircle2, AlertCircle, X, HelpCircle, CreditCard,
  Mail, Facebook, Instagram, Linkedin, Music2, MessageCircle
} from "lucide-react";
import { api } from "@/api/client";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/AuthContext";
import { validatePhone, validateEmail, validateFullName } from "@/lib/validators";
import Logo from "@/components/zeus/Logo";
import LanguageToggle from "@/components/zeus/LanguageToggle";
import ThemeToggle from "@/components/zeus/ThemeToggle";

export default function Subscriptions() {
  const { lang, dir } = useI18n();
  const isAr = lang === "ar";
  const { user } = useAuth();
  const nav = useNavigate();
  const Arrow = isAr ? ArrowLeft : ArrowRight;

  const [plans, setPlans] = useState([]);
  const [currency, setCurrency] = useState("EGP");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Modal payment state
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [notes, setNotes] = useState("");
  const [paymentImage, setPaymentImage] = useState(null);
  const [imagePreview, setImagePreview] = useState("");
  const [enlarged, setEnlarged] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await api.subscriptions.getPlans();
        if (res && res.plans) {
          setPlans(res.plans);
          if (res.currency) setCurrency(res.currency);
        }
      } catch (err) {
        console.error("Failed to load plans:", err);
        // Fallback default structure
        setPlans([
          {
            id: "STARTER",
            name: "STARTER",
            price: 99,
            period: "Month",
            features: [
              { en: "Personalized learning roadmap", ar: "خريطة تعلم مخصصة بالكامل لمستواك وأهدافك" },
              { en: "AI Assistant", ar: "المساعد الذكي ZEUS رفيقك الدراسي خطوة بخطوة" },
            ],
            badge: "Popular",
          },
          {
            id: "PRO",
            name: "PRO",
            price: 199,
            period: "Month",
            features: [
              { en: "Everything in STARTER", ar: "كل مميزات باقة STARTER" },
              { en: "Interactive quizzes after every lesson", ar: "اختبارات تفاعلية بعد كل درس لتقييم فهمك" },
              { en: "A project after every stage", ar: "مشروع عملي تطبيقي شامل بعد كل مرحلة" },
            ],
            badge: "Best Value",
          },
          {
            id: "PRIME",
            name: "PRIME",
            price: 399,
            period: "Month",
            features: [
              { en: "Everything in PRO", ar: "كل مميزات باقة PRO" },
              { en: "Job search/recommendations relevant to your field", ar: "بحث وتوصيات وظائف ذكية تطابق مجالك وخبرتك" },
              { en: "Access to a community related to your field", ar: "الانضمام لمجتمع المتخصصين والزملاء في مجالك" },
              { en: "CV functionality", ar: "أداة بناء وتحسين السيرة الذاتية الاحترافية (CV)" },
              { en: "Portfolio functionality", ar: "أداة بناء وعرض البورتفوليو العام لمشاريعك" },
            ],
            badge: "Complete",
          },
        ]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const [fieldErrors, setFieldErrors] = useState({ fullName: "", email: "", phone: "" });
  const openSubscribeModal = (plan) => {
    setSelectedPlan(plan);
    setFormError("");
    setSubmitSuccess(false);
    // Start empty by design (no pre-fill). User must type everything.
    setFullName("");
    setEmail("");
    setPhone("");
    setNotes("");
    setPaymentImage(null);
    setImagePreview("");
    setEnlarged(false);
    setFieldErrors({ fullName: "", email: "", phone: "" });
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // Instant client checks before hitting the server (server re-validates).
    const okType = /^(image\/(png|jpe?g|webp))$/.test(file.type) || /\.(png|jpe?g|webp)$/i.test(file.name || "");
    if (!okType) {
      setFormError(isAr ? "مسموح صور الإيصال فقط (PNG أو JPG)" : "Receipt images only (PNG or JPG)");
      e.target.value = "";
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setFormError(isAr ? "الصورة كبيرة — الحد الأقصى 5MB" : "Image too large — max 5MB");
      e.target.value = "";
      return;
    }
    setUploadingImage(true);
    setFormError("");
    try {
      // Public endpoint: works for pending users with no login session.
      const res = await api.subscriptions.uploadReceipt({ file });
      const url = res.file_url || res.url;
      if (!url) throw new Error("no url");
      setPaymentImage(url);
      setImagePreview(URL.createObjectURL(file));
    } catch (err) {
      // Never redirect on upload failure — stay on the form and explain.
      setFormError(err.message || (isAr ? "فشل رفع الصورة، يرجى المحاولة مرة أخرى" : "Image upload failed, try again"));
      e.target.value = "";
    } finally {
      setUploadingImage(false);
    }
  };

  const handleSubmitPayment = async (e) => {
    e.preventDefault();
    setFormError("");
    const fe = { fullName: "", email: "", phone: "" };
    const nRes = validateFullName(fullName);
    if (!nRes.ok) fe.fullName = isAr ? nRes.errorAr : nRes.errorEn;
    const eRes = validateEmail(email);
    if (!eRes.ok) fe.email = isAr ? eRes.errorAr : eRes.errorEn;
    const pRes = validatePhone(phone);
    if (!pRes.ok) fe.phone = isAr ? pRes.errorAr : pRes.errorEn;
    setFieldErrors(fe);
    const firstErr = fe.fullName || fe.email || fe.phone;
    if (firstErr) {
      setFormError(firstErr);
      return;
    }
    if (!paymentImage) {
      setFormError(isAr ? "يرجى رفع صورة إيصال أو تأكيد التحويل" : "Please upload payment transfer confirmation image");
      return;
    }

    setSubmitting(true);
    try {
      await api.subscriptions.submitPayment({
        full_name: nRes.value,
        email: eRes.value,
        phone: pRes.value,
        plan: selectedPlan.id,
        payment_image_url: paymentImage,
        notes: notes,
      });
      setSubmitSuccess(true);
    } catch (err) {
      setFormError(err.message || (isAr ? "حدث خطأ أثناء إرسال الطلب، يرجى المحاولة مرة أخرى" : "Submission failed, try again"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background" dir={dir}>
      {/* Top Header */}
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-background/80 border-b border-border/40">
        <div className="max-w-7xl mx-auto px-5 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <Logo />
          </Link>
          <div className="flex items-center gap-3">
            <LanguageToggle />
            <ThemeToggle />
            {user ? (
              <Link
                to="/app"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full border border-zeus-gold/40 text-zeus-brightgold text-xs font-semibold hover:bg-zeus-gold/10 transition"
              >
                {isAr ? "لوحة التحكم" : "Dashboard"} <Arrow style={{ width: 14, height: 14 }} />
              </Link>
            ) : (
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-zeus-gold text-zeus-midnight text-xs font-semibold hover:bg-zeus-brightgold transition shadow-gold-sm"
              >
                {isAr ? "تسجيل الدخول" : "Log in"}
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-5 py-12 lg:py-20">
        <div className="text-center max-w-3xl mx-auto mb-14 animate-fade-up">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-zeus-gold/30 bg-zeus-gold/10 text-zeus-brightgold text-xs font-semibold mb-4">
            <Sparkles style={{ width: 14, height: 14 }} />
            {isAr ? "خطط واشتراكات ZEUS" : "ZEUS Subscription Plans"}
          </div>
          <h1 className="font-heading font-extrabold text-3xl sm:text-5xl tracking-tight">
            {isAr ? (
              <>استثمر في مستقبلك مع <span className="zeus-gold-text">الخطة المناسبة لك</span></>
            ) : (
              <>Invest in your future with the <span className="zeus-gold-text">Right Plan</span></>
            )}
          </h1>
          <p className="mt-4 text-muted-foreground text-sm sm:text-base leading-relaxed">
            {isAr
              ? "اختر الخطة التي تطابق احتياجاتك في التعلم، سواء كنت تبدأ مسارك الشخصي أو تجهز نفسك لسوق العمل والمشاريع الاحترافية."
              : "Choose the plan tailored to your learning goals, from personal roadmap guidance to career-ready projects and job matching."}
          </p>
        </div>

        {/* How to subscribe — shown BEFORE the form, not after */}
        <div className="max-w-6xl mx-auto mb-10 rounded-3xl zeus-glass border border-zeus-gold/30 p-6 sm:p-8">
          <h2 className="font-heading font-extrabold text-lg sm:text-xl mb-2 flex items-center gap-2">
            <HelpCircle className="text-zeus-gold" style={{ width: 20, height: 20 }} />
            {isAr ? "إزاي تشترك في زيوس؟" : "How to subscribe to ZEUS?"}
          </h2>
          <ol className="mt-3 space-y-2 text-sm text-foreground/90 leading-relaxed list-decimal list-inside">
            <li>{isAr ? "اختار الباقة المناسبة ليك من تحت ودوس «اشترك الآن»." : "Pick your plan below and click “Subscribe Now”."}</li>
            <li>{isAr ? "حوّل المبلغ عبر فودافون كاش أو إنستاباي، واملأ الفورم برقم التليفون المصري (11 رقم) وارفع صورة إيصال التحويل." : "Transfer via Vodafone Cash or InstaPay, fill the form with your Egyptian phone (11 digits) and upload the receipt."}</li>
            <li>{isAr ? "فريق الإدارة هيراجع طلبك ويفعّل حسابك وباقتك — هتقدر تدخل بعد التفعيل فقط." : "Our admin team reviews and activates your account + plan — entry works only after activation."}</li>
          </ol>
          <div className="mt-5 rounded-2xl bg-secondary/30 border border-border/60 p-4">
            <p className="text-sm font-semibold mb-1 flex items-center gap-2">
              <MessageCircle className="text-zeus-gold" style={{ width: 16, height: 16 }} />
              {isAr ? "لمعرفة كيفية الاشتراك في زيوس برجاء التواصل معانا عبر الإيميل أو من خلال صفحات السوشيال ميديا:" : "To learn how to subscribe to ZEUS, contact us via email or social media:"}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2.5">
              <a href="mailto:zeus.eduai@gmail.com" className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-zeus-gold text-zeus-midnight text-xs font-bold hover:bg-zeus-brightgold transition">
                <Mail style={{ width: 14, height: 14 }} /> zeus.eduai@gmail.com
              </a>
              <a href="https://www.facebook.com/profile.php?id=61593983652683&mibextid=ZbWKwL" target="_blank" rel="noreferrer" title="Facebook" className="w-9 h-9 rounded-full bg-secondary/60 border border-border/60 flex items-center justify-center hover:border-zeus-gold hover:text-zeus-gold transition">
                <Facebook style={{ width: 16, height: 16 }} />
              </a>
              <a href="https://www.tiktok.com/@zeusplatform?_r=1&_t=ZS-99ag6R9rlsu" target="_blank" rel="noreferrer" title="TikTok" className="w-9 h-9 rounded-full bg-secondary/60 border border-border/60 flex items-center justify-center hover:border-zeus-gold hover:text-zeus-gold transition">
                <Music2 style={{ width: 16, height: 16 }} />
              </a>
              <a href="https://www.instagram.com/zeus.eduplatform/" target="_blank" rel="noreferrer" title="Instagram" className="w-9 h-9 rounded-full bg-secondary/60 border border-border/60 flex items-center justify-center hover:border-zeus-gold hover:text-zeus-gold transition">
                <Instagram style={{ width: 16, height: 16 }} />
              </a>
              <a href="https://www.linkedin.com/company/zeus_eduu" target="_blank" rel="noreferrer" title="LinkedIn" className="w-9 h-9 rounded-full bg-secondary/60 border border-border/60 flex items-center justify-center hover:border-zeus-gold hover:text-zeus-gold transition">
                <Linkedin style={{ width: 16, height: 16 }} />
              </a>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-24">
            <Loader2 className="text-zeus-gold animate-spin" style={{ width: 36, height: 36 }} />
          </div>
        ) : (
          <div className="grid md:grid-cols-3 gap-8 items-stretch max-w-6xl mx-auto">
            {plans.map((plan, idx) => {
              const isPrime = plan.id === "PRIME";
              const isPro = plan.id === "PRO";
              const isStarter = plan.id === "STARTER";

              return (
                <div
                  key={plan.id}
                  className={`relative flex flex-col justify-between rounded-3xl p-7 transition-all duration-300 ${
                    isPrime
                      ? "bg-gradient-to-b from-zeus-gold/15 via-card to-card border-2 border-zeus-gold shadow-gold"
                      : isPro
                      ? "zeus-glass border-zeus-gold/50 shadow-md"
                      : "zeus-glass border-border/70"
                  }`}
                >
                  {plan.badge && (
                    <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-gradient-to-r from-zeus-gold to-zeus-brightgold text-zeus-midnight text-[11px] font-extrabold shadow-sm tracking-wide uppercase">
                      {plan.badge}
                    </div>
                  )}

                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <span className="font-heading font-black text-xl tracking-wider text-foreground">
                        {plan.name}
                      </span>
                      {isPrime ? (
                        <Zap className="text-zeus-gold" style={{ width: 22, height: 22 }} />
                      ) : isPro ? (
                        <Sparkles className="text-zeus-gold" style={{ width: 20, height: 20 }} />
                      ) : (
                        <Shield className="text-muted-foreground" style={{ width: 20, height: 20 }} />
                      )}
                    </div>

                    <div className="mb-6 flex items-baseline gap-1">
                      <span className="font-heading font-extrabold text-4xl sm:text-5xl text-zeus-brightgold">
                        {plan.price}
                      </span>
                      <span className="text-muted-foreground text-sm font-medium">
                        {currency} / {isAr ? "شهر" : "Month"}
                      </span>
                    </div>

                    <div className="w-full border-t border-border/50 mb-6" />

                    <ul className="space-y-3.5 text-xs sm:text-sm">
                      {plan.features.map((feat, fIdx) => (
                        <li key={fIdx} className="flex items-start gap-2.5">
                          <span className="shrink-0 w-5 h-5 rounded-full bg-zeus-gold/15 text-zeus-gold flex items-center justify-center mt-0.5">
                            <Check style={{ width: 13, height: 13 }} strokeWidth={3} />
                          </span>
                          <span className="text-foreground/90 font-medium">
                            {typeof feat === "object" ? (isAr ? feat.ar : feat.en) : feat}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="mt-8 pt-4">
                    <button
                      onClick={() => openSubscribeModal(plan)}
                      className={`w-full py-3.5 px-5 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 transition shadow-sm ${
                        isPrime
                          ? "bg-gradient-to-r from-zeus-gold to-zeus-brightgold text-zeus-midnight hover:opacity-95 shadow-gold"
                          : isPro
                          ? "bg-zeus-gold text-zeus-midnight hover:bg-zeus-brightgold"
                          : "bg-secondary text-foreground hover:bg-secondary/80 border border-border"
                      }`}
                    >
                      <span>{isAr ? "اشترك الآن" : "Subscribe Now"}</span>
                      <Arrow style={{ width: 16, height: 16 }} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Subscription Payment Submission Modal */}
      <AnimatePresence>
        {selectedPlan && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative w-full max-w-lg rounded-3xl zeus-glass border border-zeus-gold/40 p-6 sm:p-8 overflow-y-auto max-h-[90vh] bg-card text-foreground"
            >
              <button
                onClick={() => setSelectedPlan(null)}
                className="absolute top-5 end-5 w-8 h-8 rounded-full bg-secondary/60 flex items-center justify-center hover:bg-secondary transition"
              >
                <X style={{ width: 16, height: 16 }} />
              </button>

              {/* Receipt lightbox */}
              {enlarged && paymentImage && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm" onClick={() => setEnlarged(false)}>
                  <img src={paymentImage} alt={isAr ? "صورة إيصال التحويل" : "Transfer receipt"}
                    className="max-h-[90vh] max-w-full rounded-2xl shadow-2xl border border-zeus-gold/40" onClick={(e) => e.stopPropagation()} />
                  <button onClick={() => setEnlarged(false)}
                    className="absolute top-5 end-5 w-10 h-10 rounded-full bg-secondary/80 text-foreground flex items-center justify-center hover:bg-secondary transition text-lg">
                    ×
                  </button>
                </div>
              )}

              <div className="mb-6">
                <span className="text-xs font-bold uppercase tracking-wider text-zeus-brightgold">
                  {isAr ? "طلب الاشتراك في باقة" : "Subscribe to Plan"} {selectedPlan.name}
                </span>
                <h3 className="font-heading font-extrabold text-2xl mt-1">
                  {selectedPlan.price} {currency} / {isAr ? "شهر" : "Month"}
                </h3>
                <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
                  {isAr
                    ? "يرجى تحويل المبلغ عبر فودافون كاش أو إنستاباي ثم إرفاق صورة إيصال التحويل لإتمام التفعيل."
                    : "Please submit your payment transfer confirmation details below for activation."}
                </p>
                <div className="mt-3 rounded-xl bg-secondary/30 border border-border/60 p-3">
                  <p className="text-[11px] font-semibold leading-relaxed">
                    {isAr ? "لمعرفة كيفية الاشتراك برجاء التواصل معانا عبر الإيميل أو السوشيال ميديا:" : "Need help subscribing? Contact us via email or social media:"}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <a href="mailto:zeus.eduai@gmail.com" className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-full bg-zeus-gold text-zeus-midnight text-[11px] font-bold hover:bg-zeus-brightgold transition">
                      <Mail style={{ width: 12, height: 12 }} /> zeus.eduai@gmail.com
                    </a>
                    <a href="https://www.facebook.com/profile.php?id=61593983652683&mibextid=ZbWKwL" target="_blank" rel="noreferrer" title="Facebook" className="w-8 h-8 rounded-full bg-secondary/60 border border-border/60 flex items-center justify-center hover:border-zeus-gold hover:text-zeus-gold transition">
                      <Facebook style={{ width: 14, height: 14 }} />
                    </a>
                    <a href="https://www.tiktok.com/@zeusplatform?_r=1&_t=ZS-99ag6R9rlsu" target="_blank" rel="noreferrer" title="TikTok" className="w-8 h-8 rounded-full bg-secondary/60 border border-border/60 flex items-center justify-center hover:border-zeus-gold hover:text-zeus-gold transition">
                      <Music2 style={{ width: 14, height: 14 }} />
                    </a>
                    <a href="https://www.instagram.com/zeus.eduplatform/" target="_blank" rel="noreferrer" title="Instagram" className="w-8 h-8 rounded-full bg-secondary/60 border border-border/60 flex items-center justify-center hover:border-zeus-gold hover:text-zeus-gold transition">
                      <Instagram style={{ width: 14, height: 14 }} />
                    </a>
                    <a href="https://www.linkedin.com/company/zeus_eduu" target="_blank" rel="noreferrer" title="LinkedIn" className="w-8 h-8 rounded-full bg-secondary/60 border border-border/60 flex items-center justify-center hover:border-zeus-gold hover:text-zeus-gold transition">
                      <Linkedin style={{ width: 14, height: 14 }} />
                    </a>
                  </div>
                </div>
              </div>

              {submitSuccess ? (
                <div className="py-8 text-center space-y-4">
                  <div className="w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto">
                    <CheckCircle2 style={{ width: 36, height: 36 }} />
                  </div>
                  <h4 className="font-heading font-bold text-xl">
                    {isAr ? "تم إرسال طلب الاشتراك بنجاح! 🎉" : "Request Submitted Successfully! 🎉"}
                  </h4>
                  <p className="text-sm text-muted-foreground max-w-sm mx-auto leading-relaxed">
                    {isAr
                      ? "تم استلام تفاصيل التحويل. سيقوم فريق الإدارة بمراجعة الطلب وتفعيل حسابك خلال دقائق."
                      : "We received your payment confirmation. Our admin team will activate your subscription shortly."}
                  </p>
                  <button
                    onClick={() => {
                      setSelectedPlan(null);
                      nav(user ? "/app" : "/login");
                    }}
                    className="px-6 py-3 rounded-full bg-zeus-gold text-zeus-midnight font-bold text-sm mt-3"
                  >
                    {isAr ? "متابعة" : "Continue"}
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSubmitPayment} className="space-y-4 text-start">
                  {formError && (
                    <div className="p-3 rounded-xl bg-destructive/15 border border-destructive/30 text-destructive text-xs flex items-center gap-2">
                      <AlertCircle style={{ width: 16, height: 16 }} className="shrink-0" />
                      <span>{formError}</span>
                    </div>
                  )}

                  <div>
                    <label className="block text-xs font-semibold mb-1.5">
                      {isAr ? "الاسم بالكامل *" : "Full Name *"}
                    </label>
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder={isAr ? "اكتب اسمك الثلاثي أو الرباعي" : "Enter your full name"}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-secondary/50 border border-border text-sm focus:outline-none focus:border-zeus-gold"
                      required
                      maxLength={100}
                    />
                    {fieldErrors.fullName && <p className="text-destructive text-xs mt-1">{fieldErrors.fullName}</p>}
                  </div>

                  <div>
                    <label className="block text-xs font-semibold mb-1.5">
                      {isAr ? "البريد الإلكتروني المستخدم في التسجيل *" : "Email used for registration *"}
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="your.email@example.com"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-secondary/50 border border-border text-sm focus:outline-none focus:border-zeus-gold"
                      required
                      maxLength={254}
                    />
                    {fieldErrors.email && <p className="text-destructive text-xs mt-1">{fieldErrors.email}</p>}
                  </div>

                  <div>
                    <label className="block text-xs font-semibold mb-1.5">
                      {isAr ? "رقم الهاتف المستخدم في تحويل المبلغ *" : "Phone number used to make payment *"}
                    </label>
                    <input
                      type="tel"
                      inputMode="numeric"
                      dir="ltr"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value.replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d)).replace(/[^0-9]/g, "").slice(0, 11))}
                      placeholder="01XXXXXXXXX"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-secondary/50 border border-border text-sm focus:outline-none focus:border-zeus-gold"
                      required
                      maxLength={11}
                    />
                    {fieldErrors.phone && <p className="text-destructive text-xs mt-1">{fieldErrors.phone}</p>}
                  </div>

                  <div>
                    <label className="block text-xs font-semibold mb-1.5">
                      {isAr ? "صورة إيصال التحويل (Screenshot) *" : "Payment transfer confirmation image *"}
                    </label>
                    <div className="border-2 border-dashed border-border/80 rounded-2xl p-4 text-center hover:border-zeus-gold/60 transition bg-secondary/20">
                      {paymentImage ? (
                        <div className="relative inline-block">
                          <button type="button" onClick={() => setEnlarged(true)} title={isAr ? "اضغط للتكبير" : "Click to enlarge"}
                            className="block cursor-zoom-in">
                            <img
                              src={paymentImage}
                              onError={(e) => { if (imagePreview && e.currentTarget.src !== imagePreview) e.currentTarget.src = imagePreview; }}
                              alt={isAr ? "صورة إيصال التحويل" : "Transfer receipt"}
                              className="max-h-64 rounded-xl mx-auto shadow-md border border-border/40"
                            />
                          </button>
                          <span className="block text-[11px] text-muted-foreground mt-1.5">{isAr ? "اضغط على الصورة للتكبير 🔍" : "Click image to enlarge 🔍"}</span>
                          <button
                            type="button"
                            onClick={() => { setPaymentImage(null); setImagePreview(""); setEnlarged(false); }}
                            className="absolute -top-2 -end-2 w-6 h-6 rounded-full bg-destructive text-white flex items-center justify-center text-xs"
                          >
                            ×
                          </button>
                        </div>
                      ) : (
                        <label className="cursor-pointer flex flex-col items-center gap-2">
                          {uploadingImage ? (
                            <Loader2 className="animate-spin text-zeus-gold" style={{ width: 24, height: 24 }} />
                          ) : (
                            <Upload className="text-muted-foreground" style={{ width: 24, height: 24 }} />
                          )}
                          <span className="text-xs text-muted-foreground font-medium">
                            {uploadingImage
                              ? (isAr ? "جاري الرفع..." : "Uploading...")
                              : (isAr ? "انقر لاختيار صورة إيصال التحويل" : "Click to select confirmation image")}
                          </span>
                          <input
                            type="file"
                            accept=".png,.jpg,.jpeg,.webp"
                            onChange={handleImageUpload}
                            className="hidden"
                            disabled={uploadingImage}
                          />
                        </label>
                      )}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold mb-1.5">
                      {isAr ? "ملاحظات إضافية (اختياري)" : "Additional notes (optional)"}
                    </label>
                    <textarea
                      rows={2}
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder={isAr ? "أي معلومات إضافية عن التحويل..." : "Any additional notes..."}
                      className="w-full px-3.5 py-2 rounded-xl bg-secondary/50 border border-border text-sm focus:outline-none focus:border-zeus-gold"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={submitting || uploadingImage}
                    className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-zeus-gold to-zeus-brightgold text-zeus-midnight font-bold text-sm hover:opacity-95 transition disabled:opacity-50 flex items-center justify-center gap-2 mt-4"
                  >
                    {submitting ? (
                      <Loader2 className="animate-spin" style={{ width: 18, height: 18 }} />
                    ) : (
                      <>
                        <CreditCard style={{ width: 18, height: 18 }} />
                        <span>{isAr ? "تأكيد وإرسال طلب الاشتراك" : "Submit Payment Confirmation"}</span>
                      </>
                    )}
                  </button>
                </form>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
