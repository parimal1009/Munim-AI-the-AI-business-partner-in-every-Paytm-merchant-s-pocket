import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BookOpen, IndianRupee, Package, Pause, Play, Receipt, RefreshCw, RotateCcw, ShieldCheck, TrendingDown, TrendingUp, Users, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useAuth } from "../auth";
import ActionCard from "../components/ActionCard";
import { Button, Card, ChartTip, Empty, ErrorState, Skeleton, Spinner, Stat, Title } from "../components/ui";
import { useT } from "../i18n";
import { compactInr, inr } from "../lib";

function Soundbox({ text, audioUrl, onRegen, regenBusy }: { text: string; audioUrl: string | null; onRegen: () => void; regenBusy: boolean }) {
  const { t } = useT();
  const ref = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  useEffect(() => { setPlaying(false); }, [audioUrl]);
  const toggle = () => {
    const a = ref.current;
    if (!a) return;
    if (a.paused) void a.play(); else a.pause();
  };
  return (
    <div className="fade-up relative overflow-hidden rounded-3xl bg-gradient-to-br from-paytm-navy via-[#03316f] to-sky-700 p-6 text-white shadow-xl shadow-sky-900/20">
      <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-paytm-blue/25 blur-3xl" />
      <div className="relative mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-sky-200"><Volume2 className="h-4 w-4" /> {t("home.briefing")}</div>
        <button onClick={onRegen} disabled={regenBusy} aria-label={t("home.regen")} className="rounded-xl p-2 text-sky-200 transition hover:bg-white/10">
          <RefreshCw className={`h-4 w-4 ${regenBusy ? "animate-spin" : ""}`} />
        </button>
      </div>
      <div className="relative flex items-start gap-5">
        <div className="flex shrink-0 flex-col items-center gap-3">
          <button
            onClick={toggle} disabled={!audioUrl} aria-label={playing ? t("home.pause") : t("home.play")}
            className={`grid h-16 w-16 place-items-center rounded-full bg-white text-paytm-navy shadow-lg transition hover:scale-105 active:scale-95 disabled:opacity-40 ${playing ? "pulse-ring" : ""}`}
          >
            {playing ? <Pause className="h-7 w-7" /> : <Play className="h-7 w-7 translate-x-0.5" />}
          </button>
          <div className="flex h-6 items-center gap-[3px]" aria-hidden>
            {[0, 1, 2, 3, 4, 5, 6].map((i) => (
              <span key={i} className="wave-bar" style={{ height: playing ? undefined : "20%", animationDelay: `${i * 0.12}s`, animationPlayState: playing ? "running" : "paused" }} />
            ))}
          </div>
        </div>
        <p className="text-[17px] leading-relaxed text-white/95 md:text-lg">{text}</p>
      </div>
      {audioUrl && <audio ref={ref} src={audioUrl} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} preload="auto" />}
      {!audioUrl && <p className="relative mt-3 text-xs text-sky-200">{t("home.voiceOff")}</p>}
    </div>
  );
}

export default function Home() {
  const { lang, merchant } = useAuth();
  const { t } = useT();
  const qc = useQueryClient();
  const briefing = useQuery({ queryKey: ["briefing", lang], queryFn: () => api.briefing(lang) });
  const dash = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const regen = useMutation({
    mutationFn: () => api.regenBriefing(lang),
    onSuccess: (b) => qc.setQueryData(["briefing", lang], b),
  });
  const reset = useMutation({
    mutationFn: api.reset,
    onSuccess: () => qc.invalidateQueries(),
  });

  const d = dash.data;
  const pct = d?.yesterday.pct_vs_last_week ?? null;
  const spark = d?.daily.map((x) => x.sales_paise / 100);
  const pendingCount = briefing.data?.actions.length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-paytm-navy">{t("home.greeting", { name: merchant?.owner_name ?? "" })}</h1>
          <p className="mt-1 text-slate-500">{t("home.subtitle")}</p>
        </div>
        <Button variant="ghost" busy={reset.isPending} onClick={() => reset.mutate()}><RotateCcw className="h-4 w-4" /> {t("home.reset")}</Button>
      </div>

      {briefing.isLoading ? <Skeleton className="h-44" />
        : briefing.error ? <ErrorState error={briefing.error} retry={() => briefing.refetch()} />
        : briefing.data && <Soundbox text={briefing.data.text} audioUrl={briefing.data.audio_url} onRegen={() => regen.mutate()} regenBusy={regen.isPending} />}

      <section>
        <Title sub={t("home.approvalSub")}
          right={pendingCount > 0 ? <span className="flex items-center gap-1.5 rounded-full bg-rose-50 px-3 py-1 text-xs font-bold text-rose-700"><span className="h-2 w-2 animate-pulse rounded-full bg-rose-500" />{t("home.waiting", { n: pendingCount })}</span> : undefined}>
          <span className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-paytm-blue" /> {t("home.approvalTitle")}</span>
        </Title>
        {briefing.data && briefing.data.actions.length === 0 && <Empty>{t("home.allCaughtUp")}</Empty>}
        <div className="grid gap-4 md:grid-cols-2">
          {briefing.data?.actions.map((a) => <ActionCard key={a.id} action={a} />)}
        </div>
      </section>

      {dash.isLoading && <Spinner />}
      {dash.error && <ErrorState error={dash.error} retry={() => dash.refetch()} />}
      {d && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <Stat icon={IndianRupee} label={t("home.yesterdaySales")} value={inr(d.yesterday.total_paise)} tone={pct !== null && pct < 0 ? "bad" : "good"} spark={spark}
              hint={pct !== null ? <>{pct >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}{t("home.vsLastWeek", { n: Math.abs(pct) })}</> : undefined} />
            <Stat icon={Receipt} label={t("home.upi")} value={String(d.yesterday.txns)} hint={t("home.yesterday")} tone="brand" spark={d.daily.map((x) => x.txns)} />
            <Stat icon={BookOpen} label={t("home.udhaarOverdue")} value={inr(d.khata.overdue_total_paise)} hint={t("home.customers", { n: d.khata.overdue_count })} tone="bad" />
            <Stat icon={Package} label={t("home.stockAtRisk")} value={String(d.stock_at_risk)} hint={t("home.products")} tone={d.stock_at_risk ? "warn" : "good"} />
            <Stat icon={Users} label={t("home.lapsed")} value={String(d.lapsed)} hint={t("home.toWinBack")} tone="warn" />
          </div>
          <Card>
            <Title sub={t("home.trendSub")}>{t("home.trend")}</Title>
            <div className="h-64">
              <ResponsiveContainer>
                <AreaChart data={d.daily.map((x) => ({ date: x.date.slice(5), sales: x.sales_paise / 100 }))} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
                  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#00BAF2" stopOpacity={0.5} /><stop offset="95%" stopColor="#00BAF2" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748b" }} interval={3} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#64748b" }} tickFormatter={(v: number) => compactInr(v)} width={52} tickLine={false} axisLine={false} />
                  <Tooltip content={<ChartTip money />} />
                  <Area type="monotone" dataKey="sales" name={t("home.sales")} stroke="#00BAF2" strokeWidth={2.5} fill="url(#g)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
          {d.stock_at_risk > 0 && (
            <div className="flex items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <AlertTriangle className="h-5 w-5 shrink-0" /> {t("home.stockWarn", { n: d.stock_at_risk })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
