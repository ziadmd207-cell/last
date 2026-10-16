"""
Lightweight AI Orchestrator - 3 Agents (Discovery / Planning / Execution)
Priority: Groq (free) > Gemini (free) > OpenAI > Pollinations (free, no key) > Mock
"""
import json
import os
import re

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
    load_dotenv(".env")
except Exception:
    pass

ZEUS_SYSTEM = """You are ZEUS — a real AI Learning & Career Coach and close study friend. Talk like a real Egyptian friend: warm, simple, casual. Understand short replies like "ازيك", "تمام" like a friend.
COACH BEHAVIOR: Start naturally, never a fixed block of questions. Understand the user gradually: first ask where they want to get to (field/skill + why now), then pick ONE follow-up based on their last answer (goal, current level, experience, strengths, weaknesses, confusion/doubts, learning problems, past attempts, daily/weekly time + days, purpose: job/freelance/career-change/study/personal, deadline). Never ask everything at once. Adapt dynamically — no fixed questionnaire.
After the conversation hold a clear User Profile (goal, current_level beginner/intermediate/advanced, experience, strengths, weaknesses, knowledge_gaps, interests, available_time hours+days, learning_preferences videos/reading/projects, career_goal, target_role, deadline) and build every plan from it. Respect level: beginner gets foundations first, advanced never sent back to basics.
LANGUAGE RULE: Arabic or English only. If the user writes Arabic (even with 2-3 English technical words like Frontend, React, Backend, AI, Mobile) → reply in Egyptian Arabic (عامية). If the user writes mostly English → reply in English. Never reply in any other language. Never say "as an AI".
IDENTITY SECRECY (absolute): You are Zeus, a learning companion inside the ZEUS app. NEVER mention how you work technically: no model names (ChatGPT, GPT, Groq, Gemini, Llama, Muse, AI model names of any kind), no API/provider/company names, no words like API/prompt/model/parameters/training. If asked who made you, where you come from, or what powers you, answer warmly and briefly: you are Zeus, صديقك في رحلة التعلم داخل تطبيق ZEUS (or the English equivalent) — then continue the conversation naturally. Never confirm or deny any specific technology."""

# Markers of prompt/instruction echo: if a reply contains these, the model
# echoed our own instructions instead of answering — NEVER show it to users.
_LEAK_MARKERS = (
    "json object with keys", "respond only with", "respond with valid json",
    "schema hint", "=== user said", "user said (respond", "next dimension",
    "coach rules", "reply language", "=== progress", "user learning context",
    "field_comparison", "iscomplete", "never reply in any other language",
)


def _looks_like_leak(text: str) -> bool:
    """True when text looks like echoed prompt instructions, not a real reply."""
    return any(m in (text or "").lower() for m in _LEAK_MARKERS)

REQUIRED_DIMS = ["education", "experience", "field", "style", "time", "obstacle"]

def _is_empty_val(v) -> bool:
    """Empty, or a placeholder word the LLM uses instead of admitting unknown."""
    if v in (None, "", [], {}):
        return True
    if isinstance(v, str) and v.strip().lower() in ("unknown", "none", "n/a", "null", "unspecified", "-"):
        return True
    return False


def _has_val(profile: dict, *keys) -> bool:
    """True when any of the keys holds a real persisted value (structured, not keywords)."""
    for k in keys:
        if not _is_empty_val((profile or {}).get(k)):
            return True
    return False


def _analyze_missing(profile: dict, history: str) -> list:
    """Coverage from STRUCTURED persisted values — never keyword presence.

    A dimension counts as covered only when its answer is actually saved in
    the profile, so the user is never re-asked something they answered.
    """
    profile = profile or {}
    missing = []
    if not _has_val(profile, "education", "current_role"):
        missing.append("education")
    if not _has_val(profile, "experience", "background", "current_level"):
        missing.append("experience")
    if not _has_val(profile, "goal", "interests", "target_skills", "known_skills"):
        missing.append("field")
    if not _has_val(profile, "learning_style"):
        missing.append("style")
    if not (_has_val(profile, "weekly_hours") and _has_val(profile, "available_days")):
        missing.append("time")
    if not _has_val(profile, "obstacles", "weaknesses"):
        missing.append("obstacle")
    return missing

DIM_ORDER = ["education", "experience", "field", "style", "time", "obstacle", "video_pref"]

# NOTE: No canned questions by design — every question comes from the LLM.
# _fallback_question and DIM_QUESTIONS_* were permanently removed; on LLM
# failure the agent retries once, then returns an honest retryable error.

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

_DAY_ALIASES = {
    "saturday": ["السبت", "سبت", "saturday", "sat"],
    "sunday": ["الأحد", "الاحد", "أحد", "احد", "sunday", "sun"],
    "monday": ["الاثنين", "الاثنين", "اتنين", "التنين", "monday", "mon"],
    "tuesday": ["الثلاثاء", "التلات", "تلات", "tuesday", "tue"],
    "wednesday": ["الأربعاء", "الاربع", "اربع", "wednesday", "wed"],
    "thursday": ["الخميس", "خميس", "thursday", "thu"],
    "friday": ["الجمعة", "الجمعه", "جمعة", "جمعه", "friday", "fri"],
}
_ALL_DAYS = ["saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]


def _norm_digits(text: str) -> str:
    return (text or "").translate(_AR_DIGITS)


def _user_lines(history: str) -> list:
    """User messages oldest→newest. Corrections live in later messages, so
    deterministic parsing takes the LAST stated value, not the first."""
    return [l[len("user:"):] for l in (history or "").split("\n") if l.startswith("user:")]


def _parse_weekly_hours(history: str):
    """Deterministic hours extraction: digits + hour words, per-day or per-week.
    Latest mention wins (user corrections override earlier answers)."""
    found = None
    for line in _user_lines(history):
        t = _norm_digits(line).lower()
        if not t:
            continue
        v = None
        m = re.search(r"(ساعتين|(\d+(?:\.\d+)?))\s*ساع\w*\s*(في\s*اليوم|يوميا|يومي|a\s*day|daily|per\s*day|كل\s*يوم)", t)
        if m:
            n = 2.0 if "ساعتين" in (m.group(1) or "") else float(m.group(2))
            v = round(n * 7, 1)
        else:
            m2 = re.search(r"(\d+(?:\.\d+)?)\s*(ساع\w*|hour\w*|hrs?)", t)
            if m2:
                try:
                    v = float(m2.group(1))
                except Exception:
                    v = None
            elif "ساعتين" in t:
                v = 14.0 if any(k in t for k in ["يوم", "يومي", "day", "daily"]) else 2.0
            elif re.search(r"ساعة\s*(واحدة|واحده)", t):
                v = 1.0
        if v is not None:
            found = v
    return found


def _parse_available_days(history: str):
    """Deterministic day extraction. Latest day-mentioning message wins, so a
    correction ("لأ، الأحد بس") replaces earlier days instead of merging."""
    found = None
    for line in _user_lines(history):
        t = _norm_digits(line).lower()
        if not t:
            continue
        if any(k in t for k in ["كل يوم", "طول الأسبوع", "طول الاسبوع", "يوميا", "يومياً", "every day", "daily", "all week", "7 أيام", "٧ ايام", "كل الايام"]):
            found = list(_ALL_DAYS)
            continue
        if any(k in t for k in ["weekdays", "أيام الأسبوع", "ايام الاسبوع", "أيام العمل"]):
            found = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
            continue
        days = [day for day, aliases in _DAY_ALIASES.items() if any(a in t for a in aliases)]
        # "الاتنين مع بعض" means "both (styles)" in Egyptian Arabic, not Monday
        if "مع بعض" in t and "monday" in days:
            days = [d for d in days if d != "monday"]
        # Bare "الاتنين/اتنين" is AMBIGUOUS: it means "both styles" unless the
        # line is clearly about days/schedule. Never invent a Monday from it.
        if days == ["monday"]:
            monday_only_via_etneen = any(a in t for a in ["الاتنين", "الاثنين", "اتنين", "التنين"])
            day_context = any(k in t for k in ["يوم", "ايام", "أيام", "اسبوع", "أسبوع", "فاضي", "فاضية", "متاح", "متاحة", "جدول", "days", "week", "available", "free"])
            if monday_only_via_etneen and not day_context:
                days = []
        if days:
            found = [d for d in _ALL_DAYS if d in days]
    return found


def _parse_enum(history: str):
    """Deterministic style/level/depth extraction. Latest mention wins."""
    out = {}
    for line in _user_lines(history):
        t = (line or "").lower()
        _day_ctx = any(k in t for k in ["يوم", "ايام", "أيام", "اسبوع", "أسبوع", "فاضي", "فاضية", "متاح", "جدول",
                                        "السبت", "الأحد", "الاحد", "الثلاثاء", "التلات", "الأربعاء", "الخميس", "الجمعة", "الجمعه",
                                        "saturday", "sunday", "tuesday", "wednesday", "thursday", "friday", "days", "week"])
        _bare_etneen = any(k in t for k in ["الاتنين", "الاثنين", "اتنين", "التنين"])
        if any(k in t for k in ["الاثنين مع بعض", "الاتنين مع بعض", "مختلط", "both", "mixed", "فيديو وقراءة", "قراءة وفيديو"]):
            out["learning_style"] = "mixed"
        elif _bare_etneen and not _day_ctx:
            # Bare "both" answering a style question — never a Monday here.
            out["learning_style"] = "mixed"
        elif any(k in t for k in ["فيديو", "فيديوهات", "مرئي", "video", "videos", "يوتيوب", "youtube"]):
            out["learning_style"] = "video"
        elif any(k in t for k in ["قراءة", "مقالات", "كتب", "اقرأ", "reading", "articles", "books", "docs"]):
            out["learning_style"] = "reading"
        elif any(k in t for k in ["عملي", "تطبيق", "مشاريع", "بإيدي", "hands", "practice", "practical", "projects"]):
            out["learning_style"] = "hands_on"
        if any(k in t for k in ["مبتدئ", "لسه ببدأ", "من الصفر", "صفر", "جديد", "beginner", "scratch", "from zero", "new to", "no experience", "just start"]):
            out["current_level"] = "beginner"
        elif any(k in t for k in ["متوسط", "شوية خبرة", "intermediate", "some experience"]):
            out["current_level"] = "intermediate"
        elif any(k in t for k in ["متقدم", "محترف", "خبير", "advanced", "expert", "experienced"]):
            out["current_level"] = "advanced"
        if any(k in t for k in ["تأسيس", "أساس", "basics", "fundamentals", "نظرة عامة", "overview", "من البداية"]):
            out["depth"] = "overview"
        elif any(k in t for k in ["متوازن", "balanced"]):
            out["depth"] = "balanced"
        elif any(k in t for k in ["تعمق", "تعمّق", "عميق", "deep", "advanced topics"]):
            out["depth"] = "deep"
    return out

def _extract_facts(history: str) -> dict:
    """Lightweight facts from our own conversation text (no user-phrase dictionary)."""
    t = (history or "").lower()
    facts = {"likes": [], "dislikes": [], "obstacles": []}
    # Negative sentiment markers (generic, both languages)
    neg = ["ممل", "مملة", "بكره", "مش بحب", "لا أحب", "boring", "hate", "don't like", "dont like", "dislike", "مملين"]
    pos = ["بحب", "ممتع", "ممتعة", "بحب", "love", "like", "enjoy", "ممتاز"]
    # Obstacle markers
    obs = ["معطل", "مشكلة", "صعوبة", "بتشتت", "تشتت", "مش لاقي وقت", "problem", "struggle", "difficult", "stuck", "بعاني"]
    if any(k in t for k in neg):
        facts["dislikes"].append("mentioned-negative")
    if any(k in t for k in pos):
        facts["likes"].append("mentioned-positive")
    if any(k in t for k in obs):
        facts["obstacles"].append("mentioned-obstacle")
    # Keep raw last user lines for the model to interpret precisely
    lines = [l for l in (history or "").split("\n") if l.startswith("user:")]
    facts["last_user_said"] = lines[-2:] if lines else []
    return facts

def _is_question(text: str) -> bool:
    """Detect if user message is a question to the bot (either language)."""
    if not text:
        return False
    t = text.strip()
    if "?" in t or "؟" in t:
        return True
    q_words = ["ما ", "ماذا", "ايه", "إيه", "هل ", "ليه", "ازاي", "إزاي", "what", "why", "how", "when", "where", "which", "do you", "can you", "ما الفوائد", "فايدة"]
    return any(t.lower().startswith(w) or f" {w} " in f" {t.lower()} " for w in q_words)

PROFILE_KEYS = ["goal", "current_level", "learning_style", "preferred_language",
                "weekly_hours", "available_days", "education", "experience",
                "background", "motivation", "career_intent", "depth",
                "obstacles", "video_preference", "known_skills", "target_skills",
                "strengths", "preferred_time", "deadline"]

RESERVED_KEYS = {"id", "user_id", "onboarding_step", "status", "created_date",
                 "updated_date", "created_by_id", "goal_recommendations", "skill_graph"}


def _merge_discovery_profile(base: dict, llm_patch: dict, history: str, eff_lang: str) -> dict:
    """Accumulate a rich profile across turns.

    Layers (each only fills, never invents free text):
    1. everything known so far (base),
    2. deterministic parsers over the FULL history (hours/days/style/level/
       depth/video preference — immune to LLM flakiness),
    3. fresh LLM values win when non-empty (it reads nuance best).
    """
    merged = {k: v for k, v in (base or {}).items() if k not in RESERVED_KEYS}
    try:
        det = _parse_enum(history)
        hours = _parse_weekly_hours(history)
        if hours is not None:
            det["weekly_hours"] = hours
        days = _parse_available_days(history)
        if days:
            det["available_days"] = days
        for k, v in det.items():
            if _is_empty_val(merged.get(k)) and not _is_empty_val(v):
                merged[k] = v
    except Exception:
        pass
    for k, v in (llm_patch or {}).items():
        if k in RESERVED_KEYS:
            continue
        if _is_empty_val(v):
            continue
        merged[k] = v
    merged["preferred_language"] = merged.get("preferred_language") or eff_lang
    merged["video_preference"] = "free"
    return merged


# Minimum structured DNA required before the bot may declare discovery done.
# (goal gets refined in the next step, so it is not required here.)
DNA_REQUIRED = ["current_level", "learning_style", "weekly_hours"]


COACH_PROFILE_FIELDS = ["goal", "current_level", "experience", "strengths", "weaknesses", "knowledge_gaps", "interests", "available_time", "learning_preferences", "career_goal", "target_role", "deadline"]

COACH_OPENER_AR = "هالو أنا ZEUS ☺️⚡️عرفني عن نفسك اسمك ، تخصصك ، و ايه اكبر مخاوفك في التعليم ، و ايه المسار الي حابب نبدأو مع بعض🥰"
COACH_OPENER_EN = "هالو أنا ZEUS ☺️⚡️عرفني عن نفسك اسمك ، تخصصك ، و ايه اكبر مخاوفك في التعليم ، و ايه المسار الي حابب نبدأو مع بعض🥰"


def discovery_prompt(companionName: str, lang: str, profile: dict = None, history: str = "", next_dim: str = "", user_facts: dict = None) -> str:
    profile = profile or {}
    user_facts = user_facts or {}
    skip = ["onboarding_step","status","companion_name","created_date","updated_date","id","created_by_id","goal_recommendations","skill_graph"]
    known = "\n".join([f"- {k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, (dict,list)) else v}" for k,v in profile.items() if k not in skip and v not in (None,"","null")])
    known_block = f"=== ALREADY KNOWN FROM PROFILE (NEVER re-ask) ===\n{known}\n" if known else "=== ALREADY KNOWN FROM PROFILE ===\nNothing yet — start fresh.\n"
    hist_known = ""
    if history:
        hist_known = f"\n=== CONVERSATION HISTORY (ALREADY ASKED - NEVER REPEAT SAME QUESTION) ===\n{history}\n"
    facts_block = ""
    if user_facts:
        facts_block = f"\n=== USER FACTS (collected so far - respect them, NEVER contradict) ===\n{json.dumps(user_facts, ensure_ascii=False)}\n- obstacles[] are PROBLEMS the user suffers from - never present them as advantages.\n- dislikes[] must never appear in options as positive choices.\n"
    next_block = f"\n=== NEXT DIMENSION (ask ONLY this one now): {next_dim} ===\n" if next_dim else "\n=== NEXT DIMENSION: none left - summarize warmly and set isComplete=true ===\n"
    if lang == "en":
        return f"""You are ZEUS, an AI Learning & Career Coach and true friend. Name is {companionName} but don't say it unless needed. Reply ONLY in English. Languages allowed: English or Arabic only.

{known_block}{hist_known}{facts_block}{next_block}
=== COACH RULES (strict, in order) ===
1. FIRST MESSAGE: if history is empty, open naturally with: "{COACH_OPENER_EN}" — never a fixed block of direct questions.
2b. DISAMBIGUATION (critical): the word "both/الاتنين" is AMBIGUOUS — resolve it from the PENDING question, never in isolation. If the pending question was about learning STYLE (videos vs articles), it means BOTH styles: set learning_style=mixed and NEVER treat it as a day. Only treat it as a weekday when the conversation is about DAYS/schedule. Always echo your interpretation explicitly (e.g. "Got it, a mix of both") so the user can correct you.
2. ADAPTIVE: ask EXACTLY ONE follow-up based on the user's last answer (choose from: end goal, field, current level, experience, strengths, weaknesses, confusion/biggest doubt, learning problems, past attempts, daily/weekly time + days, purpose job/freelance/career-change/study/personal, deadline). Never ask everything at once, never repeat a covered dimension.
3. If the user's last message is a QUESTION to you (not an answer), answer it briefly in 1 sentence, then ask the ONE next question. Never ignore their question.
4. Understand meaning from context: "starting from zero / no experience" = beginner — set core skills to Beginner automatically, NEVER ask them to self-rate percentages. If precise level is needed, run a quiz assessment instead.
5. OPTIONS: only when choices genuinely help AND they match the reply topic AND they don't contradict USER FACTS. Omit otherwise.
6. isComplete=true ONLY when NEXT DIMENSION is none. Then give a warm 2-sentence summary, no options, and full 12-field profile (goal, current_level, experience, strengths, weaknesses, knowledge_gaps, interests, available_time, learning_preferences, career_goal, target_role, deadline + learning_style/weekly_hours/available_days/education/obstacles/video_preference for compatibility).
7. TOTAL SECRECY: you are Zeus inside the ZEUS app. Never reveal any technical details (model/company/API names). If asked, reply warmly that you are Zeus, their learning companion, and continue naturally.
8. Be natural, not robotic: if the user corrects a previous answer, adopt the new value immediately and say so.
"""
    return f"""You are ZEUS, the user's true friend and companion. Name is {companionName} but don't say it unless needed. Reply ONLY in Egyptian Arabic (عامية). Languages allowed: Arabic or English only - never any other language.

 {known_block}{hist_known}{facts_block}{next_block}
=== RULES (strict, in order) ===
0. أول رسالة: لو لا يوجد history ابدأ طبيعياً بهذه الجملة فقط: "{COACH_OPENER_AR}" — ممنوع كتلة أسئلة ثابتة.
1b. توضيح اللبس (مهم جداً): كلمة "الاتنين" غامضة — فسّرها من السؤال المعلق فقط، أبداً بمعزل عنه. لو السؤال المعلق عن ستايل التعلم (فيديو ولا مقالات) فمعناها الاتنين مع بعض: ثبّت learning_style=mixed وممنوع منعاً باتاً اعتبارها يوم الاثنين. اعتبرها يوماً فقط لو الكلام عن الأيام/الجدول. ولازم توضح فهمك صراحة في الرد (مثلاً: تمام، ميكس فيديو وقراءة 👍) عشان المستخدم يصححك لو غلط.
1. تكيّف ديناميكي: اسأل سؤالاً واحداً فقط مبنياً على آخر إجابة (اختار من: الهدف النهائي، المجال، المستوى الحالي، الخبرة، نقاط القوة، نقاط الضعف، أكثر حاجة محيراك/سؤالك الأهم، مشاكل التعلم، محاولات سابقة، الوقت اليومي/الأسبوعي + الأيام، الغرض وظيفة/فريلانس/تغيير كارير/دراسة/شخصي، الديدلاين). ممنوع سؤال كل حاجة مرة واحدة. ممنوع الرجوع لبُعد مغطى.
2. لو آخر رسالة من المستخدم سؤال لك (مش إجابة)، جاوبه باختصار في سطر واحد، وبعدها اسأل سؤالاً واحداً فقط. لا تتجاهل سؤاله أبداً.
3. افهم المعنى من السياق وليس اللفظ. أي صياغة تعني "ببدأ من الصفر / معنديش خبرة" = مبتدئ — ثبّت المهارات الأساسية Beginner تلقائياً، وممنوع تطلب منه تقييم نفسه بنسب مئوية. لو محتاج دقة اعمل Quiz تقييم حقيقي.
4. OPTIONS: فقط عند الحاجة الحقيقية، ويجب أن تطابق موضوع الرد، وألا تتعارض مع USER FACTS (مثلاً لو يكره الكورسات المملة لا تقترح دورات كخيار ممتع).
5. obstacles[] مشاكل يعاني منها — لا تعرضها أبداً كميزات.
6. isComplete=true فقط عندما لا يوجد NEXT DIMENSION. وقتها لخص بود في جملتين بدون options مع كامل البروفايل (goal, current_level, experience, strengths, weaknesses, knowledge_gaps, interests, available_time, learning_preferences, career_goal, target_role, deadline + learning_style/weekly_hours/available_days/education/obstacles/video_preference).
7. سريّة تامة: أنت Zeus داخل تطبيق ZEUS. ممنوع منعاً باتاً ذكر أي تفاصيل تقنية (أسماء موديلات/شركات/APIs). لو سُئلت عنها رد بود: أنا Zeus صديقك في رحلة التعلم، وكمل المحادثة.
8. كن طبيعياً لا آلياً: لو المستخدم صحح إجابة سابقة اعتمد الجديدة فوراً ووضح ذلك.
"""

def roadmap_prompt(profile: dict, goal: str, lang: str, base_nodes: list = None) -> str:
    lang_txt = "Egyptian Arabic" if lang == "ar" else "English"
    base = ""
    if base_nodes:
        base = f"\nCURRICULUM FOUNDATIONS (review and heavily customize for this user):\n{json.dumps(base_nodes, ensure_ascii=False)}\n"
    
    level = (profile or {}).get("current_level", "beginner")
    weekly_hours = (profile or {}).get("weekly_hours", 10)
    known = (profile or {}).get("known_skills", []) or []
    style = (profile or {}).get("learning_style", "mixed")
    education = (profile or {}).get("education", "")

    prof = profile or {}
    full_prof = json.dumps({k: v for k, v in prof.items() if v not in (None, "", [])}, ensure_ascii=False)[:3000]
    return f"""Build a REAL, personalized, job-market-ready phased learning roadmap for the goal: {goal}
USER PROFILE (build the plan FROM this — never a fixed template):
{full_prof}
- Target Goal: {goal}
- Current Level: {level} (CRITICAL: beginner=foundations first e.g. for AI: Python → Math/Stats → Data → ML → DL → CV/NLP → Transformers → LLMs/GenAI → Deployment → Projects. intermediate=skip basics, start at architecture/state/async. advanced=scalability/perf/distributed/specialization only.)
- Known Skills: {json.dumps(known, ensure_ascii=False)} (Do NOT repeat what they already know; do NOT send advanced back to basics; do NOT throw beginners into Transformers)
- Background: {education} | Time: {weekly_hours}h/week | Style: {style} | Video: {prof.get('video_preference', 'free')}
{base}
STRICT REQUIREMENTS:
1. UNDERSTAND THE FIELD: e.g. "learn AI" must include Python foundations, Math/Stats, NumPy/Pandas, ML (regression/classification/trees/RF/SVM/KNN/clustering/eval/CV/tuning), Deep Learning (NN/backprop/CNN/RNN/LSTM), Computer Vision, NLP, Transformers, LLMs/GenAI, Deployment/MLOps, Real Projects — never just 4 shallow nodes like Pandas/Decision Tree/Model/Model.
2. DYNAMIC STRUCTURE: you decide the number of phases/weeks/lessons from goal+level+time (one Phase may be 3 weeks, a Week 4-8 lessons). Do NOT force "5 phases, 10-14 nodes". Cover the field comprehensively: 8-14 phases for big fields like AI, fewer for narrow goals.
3. LOGICAL PROGRESSION: Learn → Practice → Build → Evaluate → Advance. Each phase ends with a portfolio-worthy project.
4. REALISTIC ESTIMATES: estimated_hours calibrated to {weekly_hours}h/week. Lesson titles must come from actual content (e.g. "Python Variables & Data Types", NOT "Day 1").
5. TARGETED: every node serves {goal}. No off-topic tech.
6. STRUCTURE per node: id, title, phase, objective, skills[], estimated_hours, tasks[3-5], projects[1-2], resources[1-3 with title/type/tier/url], parent_ids.
Language: {lang_txt}.
"""

# ---------------- Core caller with free LLM chain ----------------

async def _call_hf(prompt: str, system: str, response_schema: dict = None) -> dict | None:
    """HuggingFace free Inference fallback (no visa)."""
    # Read from DB settings first, fallback to env
    try:
        cfg = _get_runtime_settings()
        hf_token = cfg.get("hf_token", "").strip() or os.getenv("HF_TOKEN", "").strip()
        hf_model = cfg.get("hf_model", "").strip() or os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    except Exception:
        hf_token = os.getenv("HF_TOKEN", "").strip()
        hf_model = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    if not hf_token:
        return None
    try:
        import httpx
        full = f"{system}\n\n{prompt}\n\nRespond ONLY with JSON, no markdown." if response_schema else f"{system}\n\n{prompt}"
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(
                f"https://api-inference.huggingface.co/models/{hf_model}",
                headers={"Authorization": f"Bearer {hf_token}", "Content-Type": "application/json"},
                json={"inputs": full, "parameters": {"max_new_tokens": 1200, "temperature": 0.7, "return_full_text": False}},
            )
            if r.status_code in (401, 403):
                print(f"HF auth fail: {r.text[:200]}")
                return None
            if r.status_code == 503:
                # Model loading — don't crash, just skip to next provider
                print(f"HF 503 (model loading), skipping")
                return None
            if r.status_code != 200:
                print(f"HF error {r.status_code}: {r.text[:300]}")
                return None
            data = r.json()
            text = ""
            if isinstance(data, list) and data:
                text = data[0].get("generated_text", "")
            elif isinstance(data, dict):
                text = data.get("generated_text", "") or str(data)
            else:
                text = str(data)
            text = re.sub(r"```json|```", "", text).strip()
            try:
                return json.loads(text)
            except:
                m = re.search(r"\{.*\}", text, re.DOTALL)
                if m:
                    try:
                        return json.loads(m.group(0))
                    except:
                        pass
                if response_schema or _looks_like_leak(text):
                    return None
                return {"reply": text[:2000]}
    except Exception as e:
        print(f"HF error: {e}")
        return None

def _get_runtime_settings() -> dict:
    """Read API keys and active provider from DB AdminSetting, with env fallback."""
    # Google retires model names regularly; a pinned retired name in the DB
    # would 404 every call, so it is treated as unset (env/default wins).
    _RETIRED_GEMINI = {"gemini-1.0-pro", "gemini-1.5-flash", "gemini-1.5-pro",
                       "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"}
    _GEMINI_FALLBACK = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash"

    def _fresh_gemini(configured: str) -> str:
        m = (configured or "").strip()
        if not m or m in _RETIRED_GEMINI:
            return _GEMINI_FALLBACK
        return m
    try:
        from ..core.database import engine
        from sqlmodel import Session
        from ..models import AdminSetting
        with Session(engine) as session:
            s = session.get(AdminSetting, "default")
            if s:
                return {
                    "groq_api_key": (s.groq_api_key or os.getenv("GROQ_API_KEY", "")).strip(),
                    "groq_model": (s.groq_model or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")).strip(),
                    "gemini_api_key": (s.gemini_api_key or os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")).strip(),
                    "gemini_model": _fresh_gemini(s.gemini_model or os.getenv("GEMINI_MODEL", "")),
                    "openai_api_key": (s.openai_api_key or os.getenv("OPENAI_API_KEY", "")).strip(),
                    "openai_model": (s.openai_model or "gpt-4o-mini").strip(),
                    "hf_token": (s.hf_token or os.getenv("HF_TOKEN", "")).strip(),
                    "hf_model": (s.hf_model or os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")).strip(),
                    "openrouter_api_key": os.getenv("OPENROUTER_API_KEY", "").strip(),
                    "openrouter_model": os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free").strip(),
                    "active_ai_provider": (s.active_ai_provider or "auto").strip().lower(),
                }
    except Exception:
        pass
    return {
        "groq_api_key": os.getenv("GROQ_API_KEY", "").strip(),
        "groq_model": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip(),
        "gemini_api_key": (os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")).strip(),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip(),
        "openai_api_key": os.getenv("OPENAI_API_KEY", "").strip(),
        "openai_model": "gpt-4o-mini",
        "hf_token": os.getenv("HF_TOKEN", "").strip(),
        "hf_model": os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct").strip(),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY", "").strip(),
        "openrouter_model": os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free").strip(),
        "active_ai_provider": "auto",
    }


async def _call_gemini_grounded(prompt: str, system: str, response_schema: dict = None, api_key: str = None, model: str = None) -> dict | None:
    """Gemini with Google Search grounding."""
    gemini_key = api_key or os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
    if not gemini_key:
        return None
    try:
        import httpx
        gemini_model = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_key}"
        full_text = f"{system}\n\n{prompt}\n\nRespond ONLY with JSON, no markdown."
        if response_schema:
            full_text += f" Schema: {json.dumps(response_schema)}"
        body = {
            "contents": [{"role": "user", "parts": [{"text": full_text}]}],
            "generationConfig": {"temperature": 0.7},
            "tools": [{"google_search": {}}],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=body)
            if r.status_code in (401, 403):
                print(f"Gemini auth fail {r.status_code}: {r.text[:300]}")
                return None
            if r.status_code == 429:
                # Free-tier per-minute quota: usually resets in seconds — wait
                # once, retry, and only then hand off. Genuine billing death is
                # surfaced only via explicit billing errors, never bare 429.
                try:
                    import asyncio
                    await asyncio.sleep(5)
                    r = await client.post(url, json=body)
                except Exception:
                    return None
                if r.status_code == 429:
                    print("Gemini 429 persists after backoff — handing off to next provider")
                    return None
            r.raise_for_status()
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            text = re.sub(r"```json|```", "", text).strip()
            try:
                return json.loads(text)
            except:
                m = re.search(r"\{.*\}", text, re.DOTALL)
                if m:
                    try:
                        return json.loads(m.group(0))
                    except:
                        pass
                if response_schema or _looks_like_leak(text):
                    return None
                return {"reply": text[:2000]}
    except Exception as e:
        print(f"Gemini grounded error: {e}")
        return None


async def _call_pollinations(prompt: str, system: str, response_schema: dict = None) -> dict | None:
    import httpx
    full_prompt = f"{system}\n\n{prompt}"
    if response_schema:
        full_prompt += f"\n\nRespond ONLY with valid JSON. No markdown, no explanation. Schema hint: {json.dumps(response_schema, ensure_ascii=False)}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://text.pollinations.ai/openai",
                json={
                    "model": "openai",
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt + ("\n\nRespond ONLY JSON." if response_schema else "")}],
                    "jsonMode": bool(response_schema),
                    "seed": 42,
                },
                headers={"Content-Type": "application/json"},
            )
            if r.status_code == 200:
                data = r.json()
                if "choices" in data and data["choices"]:
                    content = data["choices"][0]["message"]["content"]
                    if "doesn't have enough credits" in content or "top up" in content.lower():
                        return None
                    content = re.sub(r"```json|```", "", content).strip()
                    try:
                        return json.loads(content)
                    except:
                        m = re.search(r"\{.*\}", content, re.DOTALL)
                        if m:
                            try:
                                return json.loads(m.group(0))
                            except:
                                pass
                        if not response_schema and not _looks_like_leak(content):
                            return {"reply": content}
    except Exception:
        pass
    return None


async def _call_openrouter(prompt: str, system: str, response_schema: dict = None, api_key: str = None, model: str = None) -> dict | None:
    """OpenRouter (OpenAI-compatible). Free-tier models rotate — failures fall through."""
    or_key = (api_key or os.getenv("OPENROUTER_API_KEY", "")).strip()
    or_model = (model or os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")).strip()
    if not or_key:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=or_key, base_url="https://openrouter.ai/api/v1")
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        kwargs = {"model": or_model, "messages": messages, "temperature": 0.7,
                  "extra_headers": {"HTTP-Referer": "https://mohamedgamal.tech", "X-Title": "ZEUS"}}
        kwargs["max_tokens"] = 4096 if response_schema else 1024
        if response_schema:
            messages[1]["content"] += f"\n\nRespond ONLY with valid JSON matching: {json.dumps(response_schema, ensure_ascii=False)}"
        resp = await client.chat.completions.create(**kwargs)
        choices = getattr(resp, "choices", None) or []
        _msg = choices[0].message if choices and choices[0] else None
        content = (getattr(_msg, "content", None) or "").strip()
        if not content:
            print(f"OpenRouter ({or_model}) empty choices, trying next provider")
            return None
        content = re.sub(r"^```(?:json)?|```$", "", content).strip()
        try:
            return json.loads(content)
        except:
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except:
                    pass
            # Structured reply requested but unparseable, or prompt echo:
            # fall through to the next provider — never serve raw output.
            if response_schema or _looks_like_leak(content):
                print(f"OpenRouter ({or_model}) unparseable/leak, trying next provider: {content[:200]}")
                return None
            return {"reply": content}
    except Exception as e:
        msg = str(e).lower()
        if "429" in msg or "quota" in msg or "rate" in msg or "limit" in msg:
            print(f"OpenRouter rate-limited, trying next provider: {e}")
            return None
        print(f"OpenRouter error: {e}")
        return None


# Real orchestration: each task declares its provider order by strength.
# A failed provider hands the SAME task off to the next one automatically.
TASK_ROUTES = {
    "discovery": ["gemini", "openrouter", "groq"],      # dialect + memory + JSON
    "planning": ["gemini", "openrouter", "groq"],       # long structured output
    "tutor": ["gemini", "openrouter", "groq"],           # lesson Q&A understanding
    "companion": ["gemini", "openrouter", "groq"],       # contextual companion
    "review": ["gemini", "openrouter", "groq"],          # project judgment
    "quiz": ["groq", "gemini", "openrouter"],            # strict JSON, high volume
    "assessment": ["groq", "gemini", "openrouter"],      # strict JSON quiz
    "recommend": ["groq", "gemini", "openrouter"],       # short structured
    "rewrite": ["groq", "gemini", "openrouter"],         # short rewrites
    "greet": ["groq", "openrouter", "gemini"],           # short, fast
    "jobs": ["gemini", "groq", "openrouter"],            # needs grounded search
}
DEFAULT_ROUTE = ["groq", "gemini", "hf", "openai", "pollinations"]


async def _call_openai(prompt: str, system: str, response_schema: dict = None, model: str = "gpt-4o-mini", max_tokens: int = None, task: str = None) -> dict:
    cfg = _get_runtime_settings()
    active_provider = cfg.get("active_ai_provider", "auto")

    groq_key = cfg.get("groq_api_key", "")
    groq_model = cfg.get("groq_model", "openai/gpt-oss-20b")
    gemini_key = cfg.get("gemini_api_key", "")
    gemini_model = cfg.get("gemini_model", "gemini-3.8-flash")
    openai_key = cfg.get("openai_api_key", "")
    openai_model_cfg = cfg.get("openai_model", model)
    or_key = cfg.get("openrouter_api_key", "")
    or_model = cfg.get("openrouter_model", "nvidia/nemotron-3-ultra-550b-a55b:free")

    async def _try_groq():
        if not groq_key:
            return None
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
            kwargs = {"model": groq_model, "messages": messages, "temperature": 0.7}
            # openai<1.60 uses max_tokens (max_completion_tokens is newer API)
            kwargs["max_tokens"] = max_tokens or (4096 if response_schema else 1024)
            if response_schema:
                messages[1]["content"] += f"\n\nRespond ONLY with valid JSON matching: {json.dumps(response_schema, ensure_ascii=False)}"
            resp = await client.chat.completions.create(**kwargs)
            content = (resp.choices[0].message.content or "").strip()
            content = re.sub(r"^```(?:json)?|```$", "", content).strip()
            try:
                return json.loads(content)
            except:
                best = None
                for m in re.finditer(r"\{.*\}", content, re.DOTALL):
                    chunk = m.group(0)
                    if best is None or len(chunk) > len(best):
                        best = chunk
                if best:
                    try:
                        return json.loads(best)
                    except:
                        pass
                if response_schema and "nodes" in str(response_schema):
                    if re.search(r'"nodes"\s*:\s*\[', content):
                        raise ValueError("truncated-roadmap-json")
                # Structured reply requested but unparseable: fall through to the
                # next provider — NEVER serve raw model output (may be prompt echo).
                if response_schema:
                    print(f"Groq unparseable JSON, trying next provider: {content[:200]}")
                    return None
                if _looks_like_leak(content):
                    print(f"Groq leaked prompt echo, trying next provider: {content[:200]}")
                    return None
                return {"reply": content}
        except Exception as e:
            msg = str(e).lower()
            if any(k in msg for k in ("insufficient", "billing", "payment", "top up", "topup")):
                return {"credit_exhausted": True, "reply": "عذراً يا صاحبي، رصيد الـ AI خلص حالياً، جرّب بعد الشحن 💳", "error": "credit_exhausted"}
            if "429" in msg or "quota" in msg or "rate" in msg or "limit" in msg:
                # Transient rate limit — hand off to the next provider in line.
                print(f"Groq rate-limited, handing off: {e}")
                return None
            print(f"Groq error: {e}")
            return None

    async def _try_openai():
        if not openai_key:
            return None
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=openai_key)
            messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
            kwargs = {"model": openai_model_cfg, "messages": messages, "temperature": 0.7}
            if response_schema:
                kwargs["response_format"] = {"type": "json_object"}
                messages[1]["content"] += f"\n\nYou MUST respond with valid JSON matching: {json.dumps(response_schema, ensure_ascii=False)}. Respond ONLY with JSON."
            resp = await client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
            try:
                return json.loads(content)
            except:
                try:
                    m = re.search(r"\{.*\}", content, re.DOTALL)
                    if m:
                        return json.loads(m.group(0))
                except:
                    pass
                if response_schema or _looks_like_leak(content or ""):
                    print(f"OpenAI unparseable/leak, trying next provider: {(content or '')[:200]}")
                    return None
                return {"reply": content}
        except Exception as e:
            print(f"OpenAI error: {e}")
            return None

    async def _route(name: str):
        if name == "groq":
            return await _try_groq()
        if name == "gemini":
            return await _call_gemini_grounded(prompt, system, response_schema, gemini_key, gemini_model)
        if name == "openrouter":
            return await _call_openrouter(prompt, system, response_schema, or_key, or_model)
        if name in ("hf", "huggingface"):
            return await _call_hf(prompt, system, response_schema)
        if name == "openai":
            return await _try_openai()
        if name == "pollinations":
            return await _call_pollinations(prompt, system, response_schema)
        return None

    # Explicit provider pin (admin override) still respected first.
    if active_provider != "auto":
        res = await _route(active_provider)
        if res:
            return res

    # Task-based orchestration: each task walks its own provider order,
    # handing the SAME task off on failure. Pollinations stays last resort.
    route = list(TASK_ROUTES.get(task or "", []) or [])
    for name in DEFAULT_ROUTE:
        if name not in route:
            route.append(name)
    if "pollinations" in route:
        route.remove("pollinations")
    route.append("pollinations")
    for name in route:
        try:
            res = await _route(name)
        except Exception as e:
            print(f"orchestrator: provider {name} raised for task={task}: {e}")
            continue
        if res:
            if task:
                print(f"orchestrator: task={task} served by {name}")
            return res

    # All providers failed — return friendly retryable error (not 503)
    return {"error": "temporary", "retry": True, "reply": "", "toast": "حدث خطأ صغير، جرّب تاني 🙏"}

def _service_unavailable() -> dict:
    # Mock permanently removed: every provider failure surfaces as retryable error
    return {"error": "temporary", "retry": True, "reply": "", "toast": "حدث خطأ صغير"}



# ---- 3 Agents ----

def _detect_lang(text: str, fallback: str = "ar") -> str:
    """Detect dominant language: Arabic or English only."""
    if not text:
        return fallback if fallback in ("ar", "en") else "ar"
    import re
    ar = len(re.findall(r"[\u0600-\u06FF]", text))
    if ar > 0:
        en_words = len(re.findall(r"[a-zA-Z]{2,}", text))
        total_words = len(text.split()) or 1
        # Arabic with a few English tech words -> still ar
        if en_words / total_words <= 0.6:
            return "ar"
        return "en"
    en_words = len(re.findall(r"[a-zA-Z]{2,}", text))
    if en_words > 0:
        return "en"
    return fallback if fallback in ("ar", "en") else "ar"

async def discovery_agent(messages: list, profile: dict, companionName: str, lang: str) -> dict:
    hist = "\n".join([f"{m['role']}: {m['content']}" for m in messages[-12:]])
    q_count = 0
    for m in messages:
        if m["role"] == "assistant":
            c = m["content"]
            # The seeded opener is a greeting, not a question — never count it.
            if "ZEUS" in c and ("هالو" in c or "Hello" in c or "أهل" in c):
                continue
            q_count += 1
    # Server-side language detection: Arabic wins if ANY Arabic appears in the
    # whole conversation (history + last message). Explicit override only:
    # user literally asking for English ("رد بالإنجليزي", "english please"...).
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    _all_text = hist + "\n" + (last_user or "")
    _explicit_en = bool(re.search(r"(رد|تكلم|جاوب)?\s*(بالإنجليزي|بالانجليزي|بالإنجليزية)|english please|speak english|reply in english|in english please", _all_text.lower()))
    if _explicit_en:
        eff_lang = "en"
    elif re.search(r"[\u0600-\u06FF]", _all_text):
        eff_lang = "ar"
    else:
        eff_lang = _detect_lang(last_user, lang if lang in ("ar", "en") else "ar")
    # State machine: covered dims from profile + history; next = first uncovered in order
    missing = _analyze_missing(profile, hist)
    covered = [d for d in REQUIRED_DIMS if d not in missing]
    # video_pref tracked separately (profile.video_preference)
    vpref_known = bool((profile or {}).get("video_preference"))
    ordered = [d for d in DIM_ORDER if d in missing or (d == "video_pref" and not vpref_known)]
    # Derive user_facts from history (likes/dislikes/obstacles) for consistency
    user_facts = _extract_facts(hist)
    next_dim = ordered[0] if ordered else ""
    # If last user message looks like a QUESTION to the bot, flag it so bot answers first
    user_asked = _is_question(last_user)
    q_hint = "User asked YOU a question: answer it in 1 sentence FIRST, then ask NEXT DIMENSION." if user_asked else "Last message is an answer: acknowledge it briefly and warmly FIRST (so they feel heard), then ask NEXT DIMENSION."
    # Quote the exact user text so the model answers THIS question, not another topic.
    user_quote = f'\n=== USER SAID (respond to exactly this, nothing else): "{last_user}" ===' if last_user else ""
    # Corrections ("خليها 4 ساعات" after "2") must be acknowledged AND adopted.
    correction_hint = ""
    try:
        _prev_prof = {k: v for k, v in (profile or {}).items() if v not in (None, "", [], {})}
    except Exception:
        _prev_prof = {}
    if _prev_prof and last_user:
        correction_hint = "\nIf the user corrects a previous answer (new number/choice replaces an old one), acknowledge the NEW value explicitly (e.g. تمام، اعتمدت 4 ساعات) and put ONLY the new value in profile."
    lang_force = "REPLY LANGUAGE: English ONLY. All reply and options in English." if eff_lang == "en" else "REPLY LANGUAGE: Egyptian Arabic ONLY (عامية). All reply and options in Arabic."
    prompt = discovery_prompt(companionName, eff_lang, profile, history=hist, next_dim=next_dim, user_facts=user_facts) + f"\n\n=== PROGRESS: {q_count} real questions. SETTLED (covered — NEVER ask about these again): [{','.join(covered)}]. STILL UNKNOWN (ask exactly ONE of these next): [{','.join(missing)}] ===\n{q_hint}{user_quote}{correction_hint}\n{lang_force}\nRespond JSON: {{\"reply\": string (warm, simple, friendly - 1-2 sentences, answer user question first if any, then ask NEXT DIMENSION only, MUST be in required reply language), \"options\": string[] (same language as reply, ONLY when choices genuinely help AND match the reply topic AND respect USER FACTS - else omit or []), \"isComplete\": bool (true ONLY when NEXT DIMENSION is none AND profile has goal, level, style, time), \"profile\": object (MUST include every dimension covered so far: goal, current_level, learning_style, preferred_language, weekly_hours, available_days, education, experience, background, motivation, obstacles[] as problems only, video_preference free/mixed if mentioned, known_skills/target_skills if mentioned - never drop a previously known field, never write 'unknown' - omit unknown fields instead), \"field_comparison\": array (optional)}}."
    schema = {"type": "object", "properties": {"reply": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}}, "isComplete": {"type": "boolean"}, "profile": {"type": "object"}, "field_comparison": {"type": "array"}}}
    eff_system = ZEUS_SYSTEM
    if eff_lang == "en":
        eff_system = "You are ZEUS, a friendly learning companion. Reply ONLY in English. Never reply in Arabic. Keep it warm, simple, 1-2 sentences."
    result = await _call_openai(prompt, eff_system, schema, model="gpt-4o-mini", task="discovery")
    if result.get("credit_exhausted"):
        return result
    if result.get("error"):
        # Honest failure only — never a canned conversational reply.
        # Persist whatever profile we already accumulated so no answer is lost.
        try:
            result["profile"] = _merge_discovery_profile(profile, result.get("profile"), hist, eff_lang)
        except Exception:
            pass
        result["reply"] = ""
        result["isComplete"] = False
        return result
    result.setdefault("isComplete", False)
    result.setdefault("profile", {})
    # Always return the ACCUMULATED profile (never a sparse patch), so the
    # DNA screen stays rich even if the model only mentions one dimension.
    try:
        result["profile"] = _merge_discovery_profile(profile, result.get("profile"), hist, eff_lang)
    except Exception:
        pass
    merged = result["profile"] if isinstance(result.get("profile"), dict) else {}
    # Server-side completion gate: the free model often declares completion
    # early, skipping time/days/style questions. Only allow completion when
    # the state machine has no dimension left AND the DNA minimum is filled.
    # Escape hatch: after many questions, don't trap the user forever.
    required = list(DNA_REQUIRED) if q_count < 8 else ["current_level", "learning_style"]
    if result.get("isComplete") and (next_dim or any(_is_empty_val(merged.get(k)) for k in required)):
        result["isComplete"] = False
        # Steer the retry prompt at the ACTUAL gap (structured, not keywords).
        for k in required:
            if _is_empty_val(merged.get(k)):
                next_dim = {"current_level": "experience", "learning_style": "style", "weekly_hours": "time"}.get(k, next_dim)
                break
    # Fully dynamic by design: no turn cap, no forced completion, no default
    # values. The chat ends only when the DNA is genuinely complete
    # (state machine empty + DNA minimum filled), however many turns it takes.
    # Empty reply: retry the LLM once with an explicit nudge — never a canned
    # question. If it still fails, return an honest retryable error (the
    # frontend renders a retry bubble) while KEEPING the merged profile.
    reply_text = (result.get("reply") or "").strip()
    if not reply_text:
        try:
            import asyncio
            await asyncio.sleep(2)
            retry = await _call_openai(
                prompt + "\nYour previous reply was EMPTY. Answer NOW: warm 1-2 sentence reply in the required language, acknowledging the user's last message, then ask exactly ONE question for: " + (next_dim or "the most important thing you still don't know about them") + ".",
                eff_system, schema, model="gpt-4o-mini", task="discovery")
            if (retry and not retry.get("error") and not retry.get("credit_exhausted")
                    and (retry.get("reply") or "").strip()):
                result = retry
                result.setdefault("isComplete", False)
                result.setdefault("profile", {})
                try:
                    result["profile"] = _merge_discovery_profile(profile, result.get("profile"), hist, eff_lang)
                except Exception:
                    pass
                merged = result["profile"] if isinstance(result.get("profile"), dict) else {}
                reply_text = (result.get("reply") or "").strip()
        except Exception:
            pass
    if not reply_text:
        result["reply"] = ""
        result["isComplete"] = False
        return result
    # Leak guard: a prompt/instruction echo must never reach the user.
    if _looks_like_leak(reply_text):
        print(f"discovery leaked prompt echo, suppressing: {reply_text[:200]}")
        result["reply"] = ""
        result["isComplete"] = False
        return result
    # Dedup guard: if reply is identical to previous assistant reply, ask the
    # LLM once more for a DIFFERENT question — never a canned fallback.
    if messages:
        prev_assistant = [m for m in messages if m["role"] == "assistant"]
        if prev_assistant:
            prev = prev_assistant[-1]["content"].strip()
            if result["reply"].strip() == prev:
                try:
                    retry2 = await _call_openai(
                        prompt + "\nYou REPEATED your previous message word-for-word. Ask a DIFFERENT single question now for the next uncovered dimension (" + (next_dim or "whatever is still unknown") + "), in the required language.",
                        eff_system, schema, model="gpt-4o-mini", task="discovery")
                    if (retry2 and not retry2.get("error") and not retry2.get("credit_exhausted")
                            and (retry2.get("reply") or "").strip()
                            and retry2["reply"].strip() != prev
                            and not _looks_like_leak(retry2["reply"])): 
                        result = retry2
                        result.setdefault("isComplete", False)
                        result.setdefault("profile", {})
                        try:
                            result["profile"] = _merge_discovery_profile(profile, result.get("profile"), hist, eff_lang)
                        except Exception:
                            pass
                        merged = result["profile"] if isinstance(result.get("profile"), dict) else {}
                except Exception:
                    pass
    # Validate options: mismatched options are DROPPED, never replaced with
    # canned lists (no fixed text by design). Guards below only remove.
    if result.get("options"):
        reply_lower = result["reply"].lower()
        opts_text = " ".join(result["options"]).lower()
        # Contradiction guard: user dislikes something -> drop options praising it
        user_text_all = hist.lower()
        if any(k in user_text_all for k in ["ممل", "مملة", "boring", "بكره الكورسات"]) and any(k in opts_text for k in ["ممتعة", "ممتع", "fun", "enjoyable"]):
            result["options"] = [o for o in result["options"] if not any(k in o.lower() for k in ["ممتعة", "ممتع", "fun", "enjoyable"])]
        # Obstacle guard: never present user's obstacle as a positive option
        if user_facts.get("obstacles") and any(k in opts_text for k in ["ميزة", "advantage", "رائع"]):
            result["options"] = [o for o in result["options"] if not any(k in o.lower() for k in ["ميزة", "advantage"])]
        result["options"] = [o for o in result["options"] if o and len(o.strip()) > 1][:4]
        if len(result["options"]) == 0:
            result.pop("options", None)
    if result.get("isComplete"):
        result.pop("options", None)
    return result

async def planning_agent(profile: dict, goal: str, lang: str, base_nodes: list = None) -> dict:
    # Single-model QA: professional, level-customized, reviewed in same call (save tokens)
    level = (profile or {}).get("current_level", "beginner")
    known = (profile or {}).get("known_skills", []) or []
    style = (profile or {}).get("learning_style", "mixed")
    vpref = (profile or {}).get("video_preference", "free")
    extra_qa = f"\nQA SELF-CHECK (single model): level={level}, known_skills={known} (skip them, don't repeat basics if known), style={style}, video_preference={vpref} (free=youtube/docs only, mixed=may include Udemy/Coursera). Ensure sequencing prerequisites first, language match, professional depth for level, no hallucinated URLs. If weak, fix before returning."
    prompt = roadmap_prompt(profile, goal, lang, base_nodes) + extra_qa
    schema = {
        "type": "object",
        "properties": {
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"}, "title": {"type": "string"}, "phase": {"type": "number"},
                        "objective": {"type": "string"}, "skills": {"type": "array", "items": {"type": "string"}},
                        "estimated_hours": {"type": "number"}, "tasks": {"type": "array", "items": {"type": "string"}},
                        "projects": {"type": "array", "items": {"type": "string"}},
                        "resources": {"type": "array", "items": {"type": "object", "properties": {"title": {"type": "string"}, "type": {"type": "string"}, "tier": {"type": "string"}, "url": {"type": "string"}}}},
                        "parent_ids": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["id","title","phase","objective","tasks"]
                }
            }
        },
        "required": ["nodes"]
    }
    result = await _call_openai(prompt, ZEUS_SYSTEM, schema, model="gpt-4o", max_tokens=6000, task="planning")
    if result.get("credit_exhausted"):
        return result
    if "nodes" not in result or not result.get("nodes"):
        return _service_unavailable()
    return result

async def execution_agent(lesson: dict, messages: list, lang: str) -> dict:
    hist = "\n".join([f"{m['role']}: {m['content']}" for m in messages[-8:]])
    system = ZEUS_SYSTEM + "\nYou are a lesson tutor. Answer the student's ACTUAL question directly and precisely — never dodge it for another topic. Help user understand lesson, answer questions, don't give quiz answers."
    try:
        lesson_str = json.dumps(lesson, ensure_ascii=False, default=str)
    except Exception:
        lesson_str = str({k: v for k, v in (lesson or {}).items() if k in ("node_title", "phase", "summary")})
    prompt = f"Lesson: {lesson_str}\n\nConversation:\n{hist}\n\nReply in {'Egyptian Arabic' if lang=='ar' else 'English'}."
    result = await _call_openai(prompt, system, None, model="gpt-4o-mini", task="tutor")
    if result.get("credit_exhausted"):
        return result
    return result

async def recommend_goals_agent(profile: dict, goal: str, lang: str) -> dict:
    # Per-goal key_skills (fixes Backend showing HTML/CSS) + prior-experience aware
    prompt = f"Recommend 3-5 career goals for profile: {json.dumps(profile, ensure_ascii=False)}, hint: {goal}. Language: {lang}. For EACH goal return its OWN key_skills/tools specific to that field (Backend must be Node/Express/Postgres/Docker, NOT HTML/CSS; Frontend must be HTML/CSS/JS/React). Every recommendation MUST include: goal, score (0-100), reason, description, key_skills (3-8 items), tools, job_titles, why_fits. JSON {{\"recommendations\":[...], \"key_skills\": string[]}}"
    schema = {"type": "object", "properties": {"recommendations": {"type": "array"}, "key_skills": {"type": "array"}}, "required": ["recommendations"]}

    def _valid(r):
        recs = (r or {}).get("recommendations") or []
        if not isinstance(recs, list) or len(recs) < 2:
            return False
        return all(isinstance(x, dict) and x.get("goal") and x.get("key_skills") for x in recs)

    result = None
    for attempt in range(3):
        try:
            cand = await _call_openai(prompt, ZEUS_SYSTEM, schema, model="gpt-4o-mini", task="recommend")
        except Exception as e:
            print(f"recommendGoals fail (attempt {attempt+1}): {e}")
            cand = None
        if cand and cand.get("credit_exhausted"):
            return cand
        if _valid(cand):
            result = cand
            break
        result = cand
    res = result or {}
    if res.get("credit_exhausted"):
        return res
    if not _valid(res):
        return {"error": "temporary", "retry": True, "reply": "", "toast": "حدث خطأ صغير"}
    return res

async def generate_quiz_from_content(content: str, lang: str, num: int = 10) -> dict:
    """10 mixed questions (MCQ/true-false/scenario/concept/application) from actual lesson content."""
    ref = (content or "")[:6000]
    prompt = f"Generate {num} questions ONLY from this lesson content (same difficulty, no outside info). Mix types: multiple-choice (EXACTLY 4 non-empty options), true/false (EXACTLY 2 non-empty options, e.g. [\"صح\",\"خطأ\"]), scenario, concept, application. EVERY question MUST have a non-empty options array and an integer correct index pointing at the right option — a question without options is FORBIDDEN. Every question MUST be verifiably tied to the content below. Content: {ref} Language: {lang}. JSON {{\"questions\":[{{\"question\":string,\"type\":string,\"options\":[strings],\"correct\":number,\"explanation\":string}}]}}"
    schema = {"type": "object", "properties": {"questions": {"type": "array"}}}
    r = await _call_openai(prompt, ZEUS_SYSTEM, schema, model="gpt-4o-mini", task="quiz")
    if r.get("credit_exhausted"):
        return r
    return r

async def generate_assessment_quiz(goal: str, skills: list, lang: str, num: int = 5) -> dict:
    """Short placement quiz for onboarding assessment (non-beginners).

    Builds {num} MCQ questions spanning the given key skills at mixed
    easy/medium difficulty so a blended score can calibrate self-ratings.
    """
    skill_list = ", ".join((skills or [])[:8]) or goal
    prompt = (
        f"Write {num} multiple-choice placement questions to assess a learner's level in '{goal}'. "
        f"Spread questions across these skills: {skill_list}. Mix easy (2) and medium ({num - 2}) difficulty. "
        f"Each question has exactly 4 options with ONE correct answer testing real understanding, not trivia. "
        f"Language: {lang}. JSON {{\"questions\":[{{\"question\":string,\"type\":string,\"options\":[4 strings],\"correct\":number,\"explanation\":string,\"skill\":string}}]}}"
    )
    schema = {"type": "object", "properties": {"questions": {"type": "array"}}}
    r = await _call_openai(prompt, ZEUS_SYSTEM, schema, model="gpt-4o-mini", task="assessment")
    if r.get("credit_exhausted"):
        return r
    return r


async def review_project_agent(project_brief: str, submission_text: str, submission_url: str, lang: str) -> dict:
    """Review a learner's phase-project submission like a senior mentor.

    Returns {approved, score 0-100, feedback, strengths[], improvements[], next_step}.
    Pass mark is 70 — same bar as lesson quizzes.
    """
    brief = (project_brief or "")[:3000]
    sub = (submission_text or "")[:4000]
    url = (submission_url or "")[:500]
    prompt = (
        "You are a senior mentor reviewing a learner's phase project. Be encouraging but honest. "
        f"PROJECT BRIEF (what was asked): {brief} "
        f"LEARNER SUBMISSION (description of what they built): {sub} "
        f"REPO/LINK (may be empty): {url} "
        "Evaluate: does the submission genuinely attempt the brief? Is it complete and working as described? "
        "Approve (approved=true, score>=70) when the work shows real effort and covers the core requirements, "
        "even if polish is missing. Reject when it is off-topic, copy-pasted without understanding, far too thin, "
        "or missing core requirements. "
        f"Reply in {lang}. JSON {{\"approved\":boolean,\"score\":number,\"feedback\":string (2-4 sentences: what works + the single most important fix),\"strengths\":[strings],\"improvements\":[strings],\"next_step\":string}}"
    )
    schema = {"type": "object", "properties": {"approved": {"type": "boolean"}, "score": {"type": "number"}, "feedback": {"type": "string"}, "strengths": {"type": "array"}, "improvements": {"type": "array"}, "next_step": {"type": "string"}}}
    r = await _call_openai(prompt, ZEUS_SYSTEM, schema, model="gpt-4o-mini", task="review")
    if r.get("credit_exhausted"):
        return r
    return r


async def search_jobs_agent(profile: dict, cv: dict, lang: str) -> dict:
    prompt = (
        f"Recommend 5 REAL entry-level job listings for profile {json.dumps(profile, ensure_ascii=False)} "
        f"CV {json.dumps(cv, ensure_ascii=False)} lang {lang}. "
        "Prefer real postings the user can actually open (company career pages, LinkedIn, Wuzzuf for Egypt/MENA, RemoteOK/Remote for remote). "
        "RULES: every job MUST have a real, specific apply url (https://... pointing at the posting or a real search page for that exact role — never '#', never empty, never example.com). "
        "match_score is 0-100 fit vs the user's skills. required_skills/missing_skills are short skill names. "
        'JSON {"jobs": [{"title": string, "company": string, "location": string, '
        '"url": string, "apply_url": string, "match_score": number, "description": string (1-2 sentences), '
        '"required_skills": string[], "missing_skills": string[], "why_fits": string}]}'
    )
    schema = {"type": "object", "properties": {"jobs": {"type": "array"}}, "required": ["jobs"]}
    r = await _call_openai(prompt, ZEUS_SYSTEM, schema, model="gpt-4o-mini", task="jobs")
    if r.get("credit_exhausted"):
        return r
    return r

async def rewrite_text_agent(text: str, is_ar: bool, kind: str = "summary") -> dict:
    # CV + Portfolio content must ALWAYS be English ATS-friendly; auto-translate Arabic.
    if kind in ("summary", "project", "cv", "experience"):
        prompt = f"Rewrite the following {kind} as professional ATS-friendly English resume wording (action verbs, quantified impact, no Arabic, plain ASCII bullets). Auto-translate any Arabic to natural English. Text: {text}. JSON {{\"rewritten\": string}}"
    else:
        prompt = f"Rewrite {kind} professionally in {'Egyptian Arabic' if is_ar else 'English'}: {text}. JSON {{\"rewritten\": string}}"
    res = await _call_openai(prompt, ZEUS_SYSTEM, {"type":"object","properties":{"rewritten":{"type":"string"}}}, model="gpt-4o-mini", task="rewrite")
    if res.get("credit_exhausted"):
        return res
    return res.get("rewritten", res.get("reply", text))
