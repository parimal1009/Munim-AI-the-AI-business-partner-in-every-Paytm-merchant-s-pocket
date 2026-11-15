import {
  Activity, BrainCircuit, CheckCircle2, ChevronDown, Cpu, Flag, GitBranch, MessageSquareText, ShieldQuestion, TriangleAlert, Wrench, X, XCircle, type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo } from "react";
import type { StreamEvent } from "../api";
import { AGENT_LABEL } from "../lib";

export interface TraceRun { id: number; question: string; started: number }
export interface TraceItem {
  id: number; run: number; agent: string; kind: string; title: string; detail?: string; args?: string; at: number;
}

/** Converts a raw stream event into a displayable trace entry (null = not shown). */
export function toTrace(e: StreamEvent): Omit<TraceItem, "id" | "run" | "at"> | null {
  switch (e.type) {
    case "route": return { agent: "supervisor", kind: "route", title: `Routed to the ${AGENT_LABEL[e.routed_to] ?? e.routed_to}`, detail: `Reply language: ${e.language}` };
    case "agent_start": return { agent: e.agent, kind: "agent_start", title: "Agent started" };
    case "tool_call": return { agent: e.agent, kind: "tool_call", title: e.tool, args: Object.keys(e.args).length ? JSON.stringify(e.args) : "" };
    case "tool_result": return { agent: e.agent, kind: "tool_result", title: `${e.tool} returned`, detail: e.result };
    case "approval_required": return { agent: e.agent, kind: "approval_required", title: `Paused for your approval (${e.actions.length})`, detail: e.actions.map((a) => a.title).join("\n") };
    case "approved": return { agent: e.agent, kind: "approved", title: "Approved", detail: e.title };
    case "rejected": return { agent: e.agent, kind: "rejected", title: "Skipped", detail: e.title };
    case "fallback": return { agent: e.agent, kind: "fallback", title: "Model path failed; used deterministic tools" };
    case "reply_ready": return { agent: e.agent, kind: "reply_ready", title: "Reply ready" };
    default: return null;
  }
}

const KIND: Record<string, { icon: LucideIcon; ring: string; chip: string }> = {
  route: { icon: GitBranch, ring: "bg-violet-500", chip: "Routing" },
  agent_start: { icon: Cpu, ring: "bg-sky-500", chip: "Agent" },
  tool_call: { icon: Wrench, ring: "bg-amber-500", chip: "Tool call" },
  tool_result: { icon: CheckCircle2, ring: "bg-slate-500", chip: "Tool result" },
  approval_required: { icon: ShieldQuestion, ring: "bg-rose-500", chip: "Approval gate" },
  approved: { icon: CheckCircle2, ring: "bg-emerald-500", chip: "Approved" },
  rejected: { icon: XCircle, ring: "bg-slate-500", chip: "Skipped" },
  fallback: { icon: TriangleAlert, ring: "bg-orange-500", chip: "Fallback" },
  reply_ready: { icon: Flag, ring: "bg-emerald-500", chip: "Done" },
};

function prettyJson(s: string): string {
  try { return JSON.stringify(JSON.parse(s), null, 2); } catch { return s; }
}

const secs = (ms: number): string => `+${(ms / 1000).toFixed(1)}s`;

function Pipeline({ items }: { items: TraceItem[] }) {
  const has = (k: string) => items.some((i) => i.kind === k);
  const tools = items.filter((i) => i.kind === "tool_call").length;
  const agent = items.find((i) => i.kind === "agent_start" && i.agent !== "supervisor")?.agent;
  const steps = [
    { label: "Supervisor", sub: "routes", icon: GitBranch, on: has("route") },
    { label: agent ? (AGENT_LABEL[agent] ?? agent).replace(" Agent", "") : "Agent", sub: "reasons", icon: BrainCircuit, on: has("agent_start") },
    { label: "Tools", sub: tools ? `${tools} call${tools > 1 ? "s" : ""}` : "SQL/Python", icon: Wrench, on: tools > 0 },
    { label: "Approval", sub: "you decide", icon: ShieldQuestion, on: has("approval_required") },
    { label: "Reply", sub: "voice + text", icon: MessageSquareText, on: has("reply_ready") },
  ];
  return (
    <div className="flex items-start justify-between gap-1 px-1">
      {steps.map((s, i) => (
        <div key={s.label} className="flex flex-1 items-start">
          <div className="flex min-w-0 flex-1 flex-col items-center text-center">
            <div className={`grid h-9 w-9 place-items-center rounded-xl border transition ${s.on ? "border-paytm-blue bg-paytm-blue text-white shadow-md shadow-sky-200" : "border-slate-200 bg-white text-slate-400"}`}>
              <s.icon className="h-4 w-4" />
            </div>
            <div className={`mt-1 truncate text-[11px] font-semibold ${s.on ? "text-paytm-navy" : "text-slate-400"}`}>{s.label}</div>
            <div className="truncate text-[10px] text-slate-400">{s.sub}</div>
          </div>
          {i < steps.length - 1 && <div className={`mt-[18px] h-0.5 w-3 shrink-0 rounded ${steps[i + 1].on ? "bg-paytm-blue" : "bg-slate-200"}`} />}
        </div>
      ))}
    </div>
  );
}

function Timeline({ items }: { items: TraceItem[] }) {
  return (
    <ol className="relative space-y-3 pl-1">
      <span className="absolute bottom-2 left-[15px] top-2 w-px bg-slate-200" aria-hidden />
      {items.map((t) => {
        const k = KIND[t.kind] ?? KIND.agent_start;
        return (
          <li key={t.id} className="fade-up relative flex gap-3">
            <div className={`z-10 mt-0.5 grid h-[30px] w-[30px] shrink-0 place-items-center rounded-full text-white ring-4 ring-white ${k.ring}`}>
              <k.icon className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white p-2.5 shadow-sm">
              <div className="flex items-center gap-2 text-[11px]">
                <span className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-600">{k.chip}</span>
                <span className="truncate font-medium text-slate-500">{AGENT_LABEL[t.agent] ?? t.agent}</span>
                <span className="ml-auto font-mono text-slate-400">{secs(t.at)}</span>
              </div>
              <div className={`mt-1 break-words text-sm font-semibold text-slate-800 ${t.kind === "tool_call" ? "font-mono text-[13px]" : ""}`}>{t.title}</div>
              {t.args && <code className="mt-1 block break-all rounded-md bg-amber-50 px-2 py-1 text-[11px] text-amber-900">{t.args}</code>}
              {t.detail && (
                t.kind === "tool_result" ? (
                  <details className="group mt-1">
                    <summary className="flex cursor-pointer list-none items-center gap-1 text-xs font-medium text-sky-700">
                      <ChevronDown className="h-3 w-3 transition group-open:rotate-180" /> View data
                    </summary>
                    <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded-md bg-slate-900 p-2 text-[11px] leading-snug text-emerald-200">{prettyJson(t.detail)}</pre>
                  </details>
                ) : <p className="mt-1 whitespace-pre-line break-words text-xs text-slate-600">{t.detail}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export default function TraceDrawer({ open, onClose, runs, items, busy }: {
  open: boolean; onClose: () => void; runs: TraceRun[]; items: TraceItem[]; busy: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const ordered = useMemo(() => [...runs].reverse(), [runs]);
  if (!open) return null;
  const latest = ordered[0];
  const latestItems = latest ? items.filter((i) => i.run === latest.id) : [];
  const total = latestItems.length ? latestItems[latestItems.length - 1].at : 0;
  const toolCount = latestItems.filter((i) => i.kind === "tool_call").length;

  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label="Agent traces">
      <div className="fade-in absolute inset-0 bg-slate-900/30 backdrop-blur-[2px]" onClick={onClose} />
      <aside className="slide-in-right absolute inset-y-0 right-0 flex w-full max-w-[460px] flex-col bg-slate-50 shadow-2xl">
        <div className="bg-gradient-to-br from-paytm-navy to-sky-800 px-5 pb-4 pt-5 text-white">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-white/15"><Activity className="h-5 w-5" /></div>
              <div>
                <div className="text-lg font-bold leading-tight">Agent traces</div>
                <div className="flex items-center gap-1.5 text-xs text-sky-200">
                  <span className={`h-2 w-2 rounded-full ${busy ? "animate-pulse bg-emerald-400" : "bg-sky-300"}`} />
                  {busy ? "LangGraph is working live" : "LangGraph · idle"}
                </div>
              </div>
            </div>
            <button onClick={onClose} aria-label="Close traces" className="rounded-lg p-1.5 text-sky-100 transition hover:bg-white/15"><X className="h-5 w-5" /></button>
          </div>
          {latest && (
            <div className="mt-3 grid grid-cols-3 gap-2 text-center">
              {[
                { v: String(latestItems.length), l: "steps" },
                { v: String(toolCount), l: "tool calls" },
                { v: `${(total / 1000).toFixed(1)}s`, l: busy ? "so far" : "total" },
              ].map((s) => (
                <div key={s.l} className="rounded-xl bg-white/10 py-1.5">
                  <div className="text-lg font-bold leading-tight">{s.v}</div>
                  <div className="text-[10px] uppercase tracking-wider text-sky-200">{s.l}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-4">
          {!latest && (
            <div className="mt-10 text-center text-sm text-slate-500">
              <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-sky-100 text-sky-600"><Activity className="h-6 w-6" /></div>
              <p className="font-semibold text-slate-700">No activity yet</p>
              <p className="mx-auto mt-1 max-w-[280px]">Ask Munim anything. Every routing decision, tool call and approval gate will appear here live.</p>
            </div>
          )}
          {latest && (
            <>
              <section className="rounded-2xl border border-slate-200 bg-white p-3">
                <div className="mb-2 truncate text-xs font-semibold text-slate-500">“{latest.question}”</div>
                <Pipeline items={latestItems} />
              </section>
              <Timeline items={latestItems} />
              {busy && <div className="flex items-center gap-2 pl-1 text-xs text-slate-500"><span className="dot" /><span className="dot" /><span className="dot" /> waiting for next step</div>}
            </>
          )}
          {ordered.slice(1).length > 0 && (
            <section>
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Earlier questions</div>
              <div className="space-y-2">
                {ordered.slice(1).map((r) => {
                  const its = items.filter((i) => i.run === r.id);
                  return (
                    <details key={r.id} className="group rounded-xl border border-slate-200 bg-white p-3">
                      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-slate-700">
                        <ChevronDown className="h-4 w-4 shrink-0 text-slate-400 transition group-open:rotate-180" />
                        <span className="truncate">{r.question}</span>
                        <span className="ml-auto shrink-0 text-xs text-slate-400">{its.length} steps</span>
                      </summary>
                      <div className="mt-3"><Timeline items={its} /></div>
                    </details>
                  );
                })}
              </div>
            </section>
          )}
        </div>
      </aside>
    </div>
  );
}
