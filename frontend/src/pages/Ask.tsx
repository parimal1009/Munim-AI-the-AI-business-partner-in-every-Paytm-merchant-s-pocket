import { useQueryClient } from "@tanstack/react-query";
import { Activity, BookOpen, Check, Mic, Package, Send, ShieldAlert, Sparkles, Square, Volume2, VolumeX, Wallet, X, BarChart3, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, streamPost, type ApprovalCard, type Lang, type StreamEvent } from "../api";
import { useAuth } from "../auth";
import TraceDrawer, { toTrace, type TraceItem, type TraceRun } from "../components/TraceDrawer";
import { Button, ErrorState } from "../components/ui";
import { AGENT_LABEL, useRecorder } from "../lib";

interface Msg { role: "user" | "munim"; text: string; agent?: string }

const SUGGESTIONS: { q: string; icon: LucideIcon; tag: string }[] = [
  { q: "Kal ki sale kaisi rahi aur kaunsa product sabse zyada profit deta hai?", icon: BarChart3, tag: "Insights" },
  { q: "Udhaar wapas kaise aayega? Reminder bhejo", icon: BookOpen, tag: "Khata" },
  { q: "Doodh kab tak chalega? Order kar do", icon: Package, tag: "Inventory" },
  { q: "Diwali pe kya offer chalaun?", icon: Sparkles, tag: "Growth" },
  { q: "Diwali ke liye loan milega?", icon: Wallet, tag: "Finance" },
  { q: "Koi suspicious payment hai kya?", icon: ShieldAlert, tag: "Trust" },
];

const STEP_HINT: Record<string, string> = {
  route: "Choosing the right agent", agent_start: "Agent is thinking", tool_call: "Fetching your data", tool_result: "Reading the results",
  approval_required: "Waiting for your approval", fallback: "Switching to safe fallback", reply_ready: "Writing the reply",
};

export default function Ask() {
  const { lang, merchant } = useAuth();
  const qc = useQueryClient();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [runs, setRuns] = useState<TraceRun[]>([]);
  const [trace, setTrace] = useState<TraceItem[]>([]);
  const [drawer, setDrawer] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [thread, setThread] = useState<string | null>(null);
  const [pending, setPending] = useState<ApprovalCard[] | null>(null);
  const [speak, setSpeak] = useState(true);
  const rec = useRecorder();
  const audioRef = useRef<HTMLAudioElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const itemId = useRef(0);
  const runId = useRef(0);
  const runStart = useRef(Date.now());

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, pending, busy]);

  const play = useCallback((url: string) => {
    const a = audioRef.current;
    if (!a) return;
    a.src = url;
    void a.play().catch(() => undefined);
  }, []);

  const say = useCallback(async (text: string, l: Lang) => {
    try { play((await api.speak(text, l)).audio_url); } catch { /* voice is best-effort */ }
  }, [play]);

  const handle = useCallback((e: StreamEvent) => {
    const t = toTrace(e);
    if (t) setTrace((p) => [...p, { ...t, id: ++itemId.current, run: runId.current, at: Date.now() - runStart.current }]);
    if (e.type === "start") setThread(e.thread_id);
    if (e.type === "interrupt") { setPending(e.actions); setThread(e.thread_id); }
    if (e.type === "clarify") setMsgs((p) => [...p, { role: "munim", text: e.message }]);
    if (e.type === "error") setError(new Error(e.message));
    if (e.type === "final") {
      setPending(null);
      setMsgs((p) => [...p, { role: "munim", text: e.reply, agent: e.agent }]);
      if (speak) void say(e.reply.slice(0, 900), e.language);
      ["dashboard", "briefing", "actions", "khata", "inventory", "growth", "outcomes", "messages"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    }
  }, [qc, say, speak]);

  const run = useCallback(async (fn: () => Promise<void>) => {
    setBusy(true); setError(null);
    try { await fn(); } catch (err) { setError(err); } finally { setBusy(false); }
  }, []);

  const send = useCallback((text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    if (pending && thread) {  // a spoken/typed reply while approval is pending is a yes/no answer
      setMsgs((p) => [...p, { role: "user", text: q }]);
      void run(() => streamPost("/api/chat/resume", { thread_id: thread, voice_text: q }, handle));
      return;
    }
    setMsgs((p) => [...p, { role: "user", text: q }]);
    runId.current += 1;
    runStart.current = Date.now();
    setRuns((p) => [...p, { id: runId.current, question: q, started: runStart.current }]);
    void run(() => streamPost("/api/chat", { message: q, language: lang }, handle));
  }, [busy, pending, thread, lang, run, handle]);

  const decide = (decisions: Record<number, boolean>) => {
    if (!thread) return;
    setMsgs((p) => [...p, { role: "user", text: Object.values(decisions).every(Boolean) ? "Haan, approve" : "Nahi, skip" }]);
    void run(() => streamPost("/api/chat/resume", { thread_id: thread, decisions }, handle));
  };

  const toggleMic = async () => {
    if (rec.recording) {
      const blob = await rec.stop();
      if (!blob) return;
      await run(async () => {
        const r = await api.transcribe(blob, "unknown");
        if (r.text.trim()) send(r.text); else setError(new Error("Could not hear anything. Please try again."));
      });
    } else {
      try { await rec.start(); } catch { setError(new Error("Microphone permission is needed for voice.")); }
    }
  };

  const last = trace[trace.length - 1];
  const stepLabel = last ? `${AGENT_LABEL[last.agent] ?? last.agent}: ${STEP_HINT[last.kind] ?? "Working"}` : "Munim is thinking";
  const runTraceCount = runs.length ? trace.filter((t) => t.run === runId.current).length : 0;

  return (
    <div className="mx-auto flex h-[calc(100vh-8.5rem)] min-h-[520px] max-w-4xl flex-col overflow-hidden rounded-3xl border border-slate-200/80 bg-white shadow-xl shadow-slate-200/60">
      {/* header */}
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 bg-gradient-to-r from-white to-sky-50/60 px-5 py-3">
        <div className="flex items-center gap-3">
          <div className="relative grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-paytm-blue to-paytm-navy text-lg font-bold text-white shadow-md shadow-sky-200">
            म
            <span className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white ${busy ? "animate-pulse bg-amber-400" : "bg-emerald-500"}`} />
          </div>
          <div>
            <h1 className="text-base font-bold leading-tight text-paytm-navy">Ask Munim</h1>
            <p className="text-xs text-slate-500">{busy ? "Working on it…" : "Online · speaks Hindi, Marathi, Tamil & English"}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSpeak((s) => !s)} aria-pressed={speak} title={speak ? "Replies are spoken" : "Replies are silent"}
            className={`grid h-9 w-9 place-items-center rounded-xl border transition ${speak ? "border-sky-200 bg-sky-50 text-sky-700" : "border-slate-200 text-slate-400 hover:bg-slate-50"}`}
          >
            {speak ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
          </button>
          <button
            onClick={() => setDrawer(true)}
            className="group relative flex items-center gap-2 rounded-xl bg-paytm-navy px-3.5 py-2 text-sm font-semibold text-white shadow-md shadow-slate-300 transition hover:bg-[#003a85] active:scale-[0.97]"
          >
            <Activity className={`h-4 w-4 ${busy ? "animate-pulse text-emerald-300" : "text-sky-300"}`} />
            Agent traces
            {runTraceCount > 0 && <span className="rounded-full bg-paytm-blue px-1.5 py-0.5 text-[10px] font-bold leading-none">{runTraceCount}</span>}
            {busy && <span className="absolute -right-1 -top-1 h-3 w-3 animate-ping rounded-full bg-emerald-400" />}
          </button>
        </div>
      </div>

      {/* conversation */}
      <div className="flex-1 space-y-4 overflow-y-auto bg-slate-50/50 px-5 py-5" aria-live="polite">
        {msgs.length === 0 && (
          <div className="fade-up mx-auto max-w-2xl pt-4 text-center">
            <div className="mx-auto mb-3 grid h-16 w-16 place-items-center rounded-3xl bg-gradient-to-br from-paytm-blue to-paytm-navy text-3xl font-bold text-white shadow-lg shadow-sky-200">म</div>
            <h2 className="text-xl font-bold text-paytm-navy">Namaste {merchant?.owner_name?.split(" ")[0]}, kya jaanna hai?</h2>
            <p className="mt-1 text-sm text-slate-500">Type or tap the mic. Six specialist agents answer from your real Paytm data, and nothing happens without your approval.</p>
            <div className="mt-5 grid gap-2 text-left sm:grid-cols-2">
              {SUGGESTIONS.map((s) => (
                <button key={s.q} onClick={() => send(s.q)} className="card-hover group flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-3 text-left shadow-sm">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-sky-50 text-sky-600 transition group-hover:bg-paytm-blue group-hover:text-white"><s.icon className="h-4 w-4" /></div>
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{s.tag}</div>
                    <div className="text-sm font-medium text-slate-700">{s.q}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {msgs.map((m, i) => (
          <div key={i} className={`fade-up flex items-end gap-2 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            {m.role === "munim" && <div className="mb-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-gradient-to-br from-paytm-blue to-paytm-navy text-xs font-bold text-white">म</div>}
            <div className={`max-w-[80%] ${m.role === "user" ? "" : "space-y-1"}`}>
              <div className={`whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed shadow-sm ${m.role === "user" ? "rounded-br-md bg-gradient-to-br from-paytm-blue to-sky-500 text-white" : "rounded-bl-md border border-slate-200 bg-white text-slate-800"}`}>{m.text}</div>
              {m.role === "munim" && m.agent && (
                <button onClick={() => setDrawer(true)} className="ml-1 flex items-center gap-1 text-[11px] font-medium text-slate-400 transition hover:text-sky-600">
                  <Activity className="h-3 w-3" /> Answered by {AGENT_LABEL[m.agent] ?? m.agent} · see how
                </button>
              )}
            </div>
          </div>
        ))}

        {pending && (
          <div className="fade-up ml-9 max-w-[85%] space-y-2 rounded-2xl border border-rose-200 bg-gradient-to-br from-rose-50 to-white p-3 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-semibold text-rose-800"><ShieldAlert className="h-4 w-4" /> Approval needed. Say “Haan” or tap:</div>
            {pending.map((a) => (
              <div key={a.id} className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
                <div className="font-semibold text-slate-900">{a.title}</div>
                <div className="mt-0.5 text-slate-600"><b>Because:</b> {a.reason}</div>
                <Button className="mt-2" variant="success" disabled={busy} onClick={() => decide({ ...Object.fromEntries(pending.map((p) => [p.id, false])), [a.id]: true })}><Check className="h-4 w-4" /> Approve this</Button>
              </div>
            ))}
            <div className="flex gap-2">
              <Button variant="success" disabled={busy} onClick={() => decide(Object.fromEntries(pending.map((p) => [p.id, true])))}><Check className="h-4 w-4" /> Haan, approve all</Button>
              <Button variant="danger" disabled={busy} onClick={() => decide(Object.fromEntries(pending.map((p) => [p.id, false])))}><X className="h-4 w-4" /> Nahi</Button>
            </div>
          </div>
        )}

        {busy && !pending && (
          <div className="fade-up flex items-end gap-2">
            <div className="mb-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-gradient-to-br from-paytm-blue to-paytm-navy text-xs font-bold text-white">म</div>
            <button onClick={() => setDrawer(true)} className="flex items-center gap-3 rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-2.5 shadow-sm transition hover:border-sky-300">
              <span className="flex gap-1"><span className="dot" /><span className="dot" /><span className="dot" /></span>
              <span className="text-xs font-medium text-slate-500">{stepLabel}</span>
            </button>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {error !== null && <div className="border-t border-slate-100 px-5 pt-3"><ErrorState error={error} /></div>}

      {/* composer */}
      <form className="flex items-center gap-2 border-t border-slate-100 bg-white p-4" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <button type="button" onClick={() => void toggleMic()} aria-label={rec.recording ? "Stop recording" : "Start voice input"}
          className={`grid h-12 w-12 shrink-0 place-items-center rounded-full text-white shadow-md transition active:scale-95 ${rec.recording ? "pulse-ring bg-rose-600" : "bg-gradient-to-br from-paytm-navy to-sky-700"}`}>
          {rec.recording ? <Square className="h-4 w-4" /> : <Mic className="h-5 w-5" />}
        </button>
        <input value={input} onChange={(e) => setInput(e.target.value)} maxLength={600} aria-label="Message"
          placeholder={rec.recording ? "Listening… tap the square to send" : pending ? "Say or type Haan / Nahi…" : "Munim se poochiye…"}
          className="h-12 flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 text-[15px] outline-none transition focus:border-paytm-blue focus:bg-white focus:ring-4 focus:ring-sky-100" />
        <button type="submit" disabled={busy || !input.trim()} aria-label="Send"
          className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-paytm-blue text-white shadow-md shadow-sky-200 transition hover:bg-sky-500 active:scale-95 disabled:opacity-40">
          <Send className="h-5 w-5" />
        </button>
      </form>
      <audio ref={audioRef} className="hidden" />
      <TraceDrawer open={drawer} onClose={() => setDrawer(false)} runs={runs} items={trace} busy={busy} />
    </div>
  );
}
