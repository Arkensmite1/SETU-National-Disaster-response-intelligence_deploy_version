import React, { useEffect, useRef, useState } from "react";
import { API, endpoints } from "@/lib/api";
import { SectionHeading, Panel } from "@/components/common/GovUI";
import { Button } from "@/components/ui/button";
import { Send, MessagesSquare, Mic, MicOff, Loader2 } from "lucide-react";
import { toast } from "sonner";

const QUICK = [
  "Where is my nearest safe shelter?",
  "What medicines should I keep for flood?",
  "मेरे घर में पानी घुस रहा है, क्या करूँ?",
  "How to evacuate elderly persons safely?",
  "Is drinking water safe after flood?",
];

export default function Chatbot() {
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Namaste! I am Setu — your national disaster-response assistant. Ask me in Hindi, English or any Indian language. For life-threatening emergencies, please dial 1078." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const scrollRef = useRef();
  const sessionId = useRef(crypto.randomUUID?.() || String(Date.now()));
  const recognitionRef = useRef(null);

  useEffect(() => { scrollRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }); }, [messages]);

  const send = async (text) => {
    const msg = (text ?? input).trim();
    if (!msg || busy) return;
    setMessages(m => [...m, { role: "user", text: msg }]);
    setInput("");
    setBusy(true);
    setMessages(m => [...m, { role: "assistant", text: "" }]);

    try {
      const res = await fetch(`${API}${endpoints.chatStream}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId.current, message: msg }),
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop();
        for (const p of parts) {
          const line = p.replace(/^data:\s*/, "").trim();
          if (!line) continue;
          try {
            const j = JSON.parse(line);
            if (j.delta) {
              setMessages(m => {
                const copy = [...m];
                copy[copy.length - 1] = { role: "assistant", text: copy[copy.length - 1].text + j.delta };
                return copy;
              });
            }
            if (j.error) toast.error(j.error);
          } catch {}
        }
      }
    } catch (e) {
      toast.error("AI unavailable. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const toggleMic = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return toast.error("Voice input not supported on this browser.");
    if (listening) { recognitionRef.current?.stop(); setListening(false); return; }
    const rec = new SR();
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.onresult = (e) => { const t = e.results[0][0].transcript; setInput(t); rec.stop(); setListening(false); send(t); };
    rec.onerror = () => setListening(false);
    rec.onend = () => setListening(false);
    rec.start(); setListening(true); recognitionRef.current = rec;
  };

  return (
    <div className="max-w-[1200px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Module 15 · 16" title="Setu — AI Emergency Assistant" description="Multilingual chatbot + voice — powered by advanced AI. Streaming responses, works during a crisis." />

      <Panel title={<span className="flex items-center gap-2"><MessagesSquare size={16} /> Setu Chat</span>}>
        <div ref={scrollRef} className="h-[480px] overflow-y-auto space-y-3 pr-2" data-testid="chat-scroll">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] px-3 py-2 rounded-md text-sm ${m.role === "user" ? "bg-national text-white" : "bg-slate-100 text-slate-800"}`} data-testid={`chat-msg-${i}`}>
                {m.text || (busy && i === messages.length - 1 ? <Loader2 size={14} className="animate-spin" /> : null)}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {QUICK.map((q) => (
            <button key={q} onClick={() => send(q)} data-testid={`quick-${q.slice(0, 10)}`}
              className="text-xs px-2.5 py-1 border border-slate-200 rounded-full hover:border-national text-slate-700">
              {q}
            </button>
          ))}
        </div>

        <div className="mt-3 flex items-center gap-2">
          <input
            data-testid="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Type in Hindi, English, Bengali, Tamil…"
            className="flex-1 border border-slate-200 rounded-md px-3 py-2 text-sm"
          />
          <Button onClick={toggleMic} variant="outline" className="gap-1" data-testid="btn-mic">
            {listening ? <MicOff size={14} className="text-status-critical" style={{ color: "#C62828" }} /> : <Mic size={14} />}
          </Button>
          <Button onClick={() => send()} disabled={busy} className="bg-national text-white gap-1" data-testid="btn-send-chat">
            <Send size={14} /> Send
          </Button>
        </div>
      </Panel>
    </div>
  );
}
