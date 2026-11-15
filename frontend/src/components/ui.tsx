import { AlertTriangle, Inbox, Loader2, type LucideIcon } from "lucide-react";
import { Component, useEffect, useState, type ButtonHTMLAttributes, type CSSProperties, type ErrorInfo, type ReactNode } from "react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`fade-up rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm ${className}`}>{children}</div>;
}

export function Title({ children, sub, right }: { children: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h2 className="text-base font-semibold text-paytm-navy">{children}</h2>
        {sub && <p className="mt-0.5 text-sm text-slate-500">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function PageHeader({ title, sub, icon: Icon, right }: { title: string; sub?: string; icon?: LucideIcon; right?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        {Icon && (
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-paytm-blue to-sky-600 text-white shadow-md shadow-sky-200">
            <Icon className="h-5 w-5" />
          </div>
        )}
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-paytm-navy">{title}</h1>
          {sub && <p className="text-sm text-slate-500">{sub}</p>}
        </div>
      </div>
      {right}
    </div>
  );
}

type Tone = "good" | "bad" | "warn" | "brand" | "neutral";
const TONE: Record<Tone, { text: string; bg: string; stroke: string }> = {
  good: { text: "text-emerald-600", bg: "bg-emerald-50 text-emerald-600", stroke: "#10B981" },
  bad: { text: "text-rose-600", bg: "bg-rose-50 text-rose-600", stroke: "#F43F5E" },
  warn: { text: "text-amber-600", bg: "bg-amber-50 text-amber-600", stroke: "#F59E0B" },
  brand: { text: "text-sky-600", bg: "bg-sky-50 text-sky-600", stroke: "#00BAF2" },
  neutral: { text: "text-slate-500", bg: "bg-slate-100 text-slate-600", stroke: "#64748B" },
};

export function Stat({ label, value, hint, tone = "neutral", icon: Icon, spark }: {
  label: string; value: string; hint?: ReactNode; tone?: Tone; icon?: LucideIcon; spark?: number[];
}) {
  const t = TONE[tone];
  return (
    <div className={`card-hover fade-up relative overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm ${spark ? "pb-12" : ""}`}>
      <div className="flex items-start justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
        {Icon && <div className={`grid h-8 w-8 place-items-center rounded-xl ${t.bg}`}><Icon className="h-4 w-4" /></div>}
      </div>
      <div className="mt-1.5 text-2xl font-bold tracking-tight text-paytm-navy">{value}</div>
      {hint && <div className={`mt-0.5 flex items-center gap-1 text-sm font-medium ${t.text}`}>{hint}</div>}
      {spark && spark.length > 1 && (
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 opacity-70">
          <ResponsiveContainer>
            <AreaChart data={spark.map((v) => ({ v }))} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={`sp-${tone}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={t.stroke} stopOpacity={0.35} /><stop offset="100%" stopColor={t.stroke} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="v" stroke={t.stroke} strokeWidth={1.5} fill={`url(#sp-${tone})`} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" | "success"; busy?: boolean };
export function Button({ variant = "primary", busy, className = "", children, disabled, ...rest }: BtnProps) {
  const styles = {
    primary: "bg-paytm-blue text-white shadow-sm shadow-sky-200 hover:bg-sky-500",
    ghost: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
    danger: "bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100",
    success: "bg-emerald-600 text-white shadow-sm shadow-emerald-200 hover:bg-emerald-700",
  }[variant];
  return (
    <button
      {...rest}
      disabled={disabled || busy}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-60 ${styles} ${className}`}
    >
      {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function Badge({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "red" | "green" | "amber" | "blue" }) {
  const t = {
    slate: "bg-slate-100 text-slate-700", red: "bg-rose-100 text-rose-700", green: "bg-emerald-100 text-emerald-700",
    amber: "bg-amber-100 text-amber-800", blue: "bg-sky-100 text-sky-700",
  }[tone];
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${t}`}>{children}</span>;
}

export function Skeleton({ className = "", style }: { className?: string; style?: CSSProperties }) {
  return <div className={`skeleton ${className}`} style={style} aria-hidden />;
}

const SLOW_HINTS = [
  "Munim is reading your latest sales",
  "Checking stock, udhaar and offers",
  "Almost there, fetching fresh numbers",
];

/** Page loader: branded status pill, a progress bar, and a skeleton shaped like the real page. */
export function Spinner({ label = "Loading" }: { label?: string }) {
  const [step, setStep] = useState(-1);
  useEffect(() => {
    const timers = [2500, 6000, 10000].map((ms, i) => window.setTimeout(() => setStep(i), ms));
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, []);
  return (
    <div role="status" aria-live="polite" className="fade-in space-y-6 py-2">
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="loader-orb grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-paytm-blue to-sky-600 text-white">
            <Loader2 className="h-4 w-4 animate-spin" />
          </div>
          <div>
            <div className="text-sm font-semibold text-paytm-navy">{label}…</div>
            <div className="h-4 text-xs text-slate-500 transition-opacity">{step >= 0 ? `${SLOW_HINTS[step]}…` : "Just a moment"}</div>
          </div>
        </div>
        <div className="loader-bar" />
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="space-y-3 rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm" style={{ animationDelay: `${i * 80}ms` }}>
            <div className="flex items-center justify-between"><Skeleton className="h-3 w-20" /><Skeleton className="h-8 w-8 !rounded-xl" /></div>
            <Skeleton className="h-7 w-24" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </div>
      <div className="space-y-4 rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
        <div className="space-y-2"><Skeleton className="h-4 w-40" /><Skeleton className="h-3 w-64" /></div>
        <div className="flex h-44 items-end gap-2">
          {[40, 65, 50, 80, 60, 90, 70, 55, 85, 45, 75, 60].map((h, i) => <Skeleton key={i} className="flex-1 !rounded-md" style={{ height: `${h}%` }} />)}
        </div>
      </div>
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const msg = error instanceof Error ? error.message : "Something went wrong";
  return (
    <div role="alert" className="flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-800">
      <AlertTriangle className="h-5 w-5 shrink-0" />
      <span className="flex-1 text-sm">{msg}</span>
      {retry && <Button variant="ghost" onClick={retry}>Retry</Button>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-slate-50/60 p-6 text-center text-sm text-slate-500">
      <Inbox className="h-5 w-5 text-slate-400" />
      {children}
    </div>
  );
}

/** Shared tooltip for Recharts so all charts look consistent. */
export function ChartTip({ active, payload, label, money = false }: {
  active?: boolean; payload?: { name?: string; value?: number | string; color?: string }[]; label?: string | number; money?: boolean;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white/95 px-3 py-2 text-xs shadow-lg backdrop-blur">
      {label !== undefined && <div className="mb-1 font-semibold text-slate-700">{label}</div>}
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 text-slate-600">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          <span>{p.name}</span>
          <span className="ml-auto pl-3 font-semibold text-slate-900">
            {money && typeof p.value === "number" ? `₹${Math.round(p.value).toLocaleString("en-IN")}` : p.value}
          </span>
        </div>
      ))}
    </div>
  );
}

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error(error, info); }
  render() {
    if (this.state.error) {
      return (
        <div className="p-8">
          <ErrorState error={this.state.error} retry={() => this.setState({ error: null })} />
        </div>
      );
    }
    return this.props.children;
  }
}
