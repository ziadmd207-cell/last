import React, { useState, useEffect, useRef } from "react";
import { MessageSquare, Loader2, Send } from "lucide-react";
import { api } from "@/api/client";
import { useI18n } from "@/lib/i18n";
import { useProfile } from "@/lib/ProfileContext";
import ChatPanel from "@/components/zeus/ChatPanel";

export default function Companion() {
  const { t, lang, dir } = useI18n();
  const { profile } = useProfile();
  const isAr = lang === "ar";
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [typing, setTyping] = useState(false);
  const [roadmap, setRoadmap] = useState(null);
  const [currentTask, setCurrentTask] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const r = await api.entities.Roadmap.filter({ status: "active" }, "-created_date", 1);
      if (r.length) setRoadmap(r[0]);
      const tk = await api.entities.Task.filter({ status: { $ne: "done" } }, "order", 1);
      if (tk.length) setCurrentTask(tk[0]);
      const conv = await api.entities.Conversation.filter({ type: "companion" }, "-created_date", 1);
      if (conv.length) {
        setConversation(conv[0]);
        setMessages(conv[0].messages || []);
      } else {
        // No fixed greeting by design: first message is crafted by the LLM
        // from the user's real goal/progress.
        const c = await api.entities.Conversation.create({
          type: "companion", companion_name: profile?.companion_name || "ZEUS", messages: [],
        });
        setConversation(c);
        setMessages([]);
        try {
          const res = await api.functions.invoke("companionChat", {
            messages: [], profile, roadmap: r[0], currentTask: tk[0],
            companionName: profile?.companion_name, lang, greet: true,
          });
          const data = res.data || res;
          const txt = (data.reply || "").trim();
          if (txt) {
            const greet = [{ role: "assistant", content: txt, ts: new Date().toISOString() }];
            setMessages(greet);
            await api.entities.Conversation.update(c.id, { messages: greet });
          }
        } catch {}
      }
      setLoading(false);
    })();
  }, []);

  const send = async (text) => {
    const userMsg = { role: "user", content: text, ts: new Date().toISOString() };
    const next = [...messages, userMsg];
    setMessages(next);
    setTyping(true);
    try {
      const res = await api.functions.invoke("companionChat", {
        messages: next.map((m) => ({ role: m.role, content: m.content })),
        profile, roadmap, currentTask, companionName: profile?.companion_name, lang
      });
      const data = res.data || res;
      const replyText = (data.reply || "").trim();
      const aiMsg = { role: "assistant", content: replyText || (isAr ? "حصل خطأ، جرّب تاني" : "An error occurred, try again"), ts: new Date().toISOString() };
      const updated = [...next, aiMsg];
      setMessages(updated);
      await api.entities.Conversation.update(conversation.id, { messages: updated });
    } catch (e) {
      setMessages([...next, { role: "assistant", content: isAr ? "حصل خطأ، جرّب تاني" : "An error occurred, try again", ts: new Date().toISOString() }]);
    } finally {
      setTyping(false);
    }
  };

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="text-zeus-gold animate-spin" style={{ width: 28, height: 28 }} /></div>;

  return (
    <div dir={dir} className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-zeus-gold to-zeus-brightgold flex items-center justify-center"><MessageSquare className="text-white" style={{ width: 22, height: 22 }} /></div>
        <div>
          <h1 className="font-heading font-extrabold text-2xl">{profile?.companion_name || "ZEUS"}</h1>
          <p className="text-xs text-muted-foreground">{isAr ? "رفيقك في التعلّم — فاهم خريطتك ومهامك" : "Your learning companion — knows your roadmap & tasks"}</p>
        </div>
      </div>
      <div className="zeus-glass p-5 h-[65vh] flex flex-col">
        <ChatPanel messages={messages} onSend={send} typing={typing} placeholder={t("companion.placeholder")} companionName={profile?.companion_name} t={t} lang={lang} />
      </div>
    </div>
  );
}