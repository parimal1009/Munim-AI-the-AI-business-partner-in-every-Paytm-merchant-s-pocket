import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Megaphone, Sparkles, UserCheck, UserMinus, Users } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import ActionCard from "../components/ActionCard";
import { Badge, Button, Card, ChartTip, Empty, ErrorState, PageHeader, Spinner, Stat, Title } from "../components/ui";
import { inr } from "../lib";

export default function Growth() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["growth"], queryFn: api.growth });
  const acts = useQuery({ queryKey: ["actions"], queryFn: api.actions });
  const sim = useMutation({
    mutationFn: (id: number) => api.simulate(id),
    onSuccess: () => { ["growth", "dashboard", "outcomes"].forEach((k) => void qc.invalidateQueries({ queryKey: [k] })); },
  });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  const d = q.data!;
  const campActions = acts.data?.filter((a) => a.kind === "campaign") ?? [];
  const funnel = [
    { name: "Known customers", v: d.stats.known_customers, c: "#BFE9F8" },
    { name: "Active (30d)", v: d.stats.active_30d, c: "#00BAF2" },
    { name: "Lapsed regulars", v: d.stats.lapsed, c: "#F43F5E" },
    { name: "Came back", v: d.campaigns.reduce((a, c) => a + c.redeemed, 0), c: "#10B981" },
  ];
  return (
    <div className="space-y-5">
      <PageHeader icon={Sparkles} title="Growth" sub="Finds regulars who stopped visiting and runs cashback offers to win them back." right={<Badge tone="blue">Growth Agent</Badge>} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={Users} label="Known customers" value={String(d.stats.known_customers)} tone="brand" />
        <Stat icon={UserCheck} label="Active (30 days)" value={String(d.stats.active_30d)} tone="good" />
        <Stat icon={UserMinus} label="Lapsed regulars" value={String(d.stats.lapsed)} tone="bad" hint="4+ visits, gone 30+ days" />
        <Stat icon={Megaphone} label="Campaigns" value={String(d.campaigns.length)} tone="neutral" />
      </div>
      {campActions.map((a) => <ActionCard key={a.id} action={a} />)}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <Title sub="From your customer base to customers won back">Customer funnel</Title>
          <div className="h-60">
            <ResponsiveContainer>
              <BarChart data={funnel} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#334155" }} width={104} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTip />} cursor={{ fill: "#f1f5f9" }} />
                <Bar dataKey="v" name="Customers" radius={[0, 8, 8, 0]} barSize={22}>{funnel.map((f) => <Cell key={f.name} fill={f.c} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <Title sub="Live cashback campaigns. In production redemptions arrive from Paytm payments; here you can simulate customers walking in.">Campaigns</Title>
          {d.campaigns.length === 0 ? <Empty>No campaigns yet. Approve the win-back suggestion above, or ask Munim “Diwali pe kya offer chalaun?”</Empty> : (
            <div className="space-y-3">
              {d.campaigns.map((c) => {
                const pct = c.targets ? Math.round((c.redeemed / c.targets) * 100) : 0;
                return (
                  <div key={c.id} className="rounded-xl border border-slate-200 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div><div className="font-semibold text-slate-900">{c.name}</div><div className="text-sm text-slate-500">{inr(c.cashback_paise)} cashback · {c.targets} customers targeted</div></div>
                      <div className="text-right"><div className="text-2xl font-bold text-emerald-600">{c.redeemed}<span className="text-sm font-medium text-slate-400"> / {c.targets}</span></div><div className="text-xs text-slate-500">came back ({pct}%)</div></div>
                    </div>
                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-emerald-600 transition-all duration-700" style={{ width: `${pct}%` }} /></div>
                    <p className="mt-3 rounded-lg bg-slate-50 p-2.5 text-sm text-slate-700">{c.offer_text}</p>
                    <Button className="mt-3" variant="ghost" busy={sim.isPending && sim.variables === c.id} onClick={() => sim.mutate(c.id)}>Simulate customers redeeming</Button>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>
      <Card>
        <Title sub="Regulars with 4+ visits who have not shopped in 30+ days, ranked by lifetime spend">Lapsed regulars</Title>
        <div className="grid gap-2 md:grid-cols-2">
          {d.lapsed.slice(0, 10).map((c) => (
            <div key={c.customer_id} className="flex items-center gap-3 rounded-xl border border-slate-200 px-3 py-2.5 text-sm transition hover:bg-slate-50">
              <div className="grid h-8 w-8 place-items-center rounded-full bg-rose-50 text-xs font-bold text-rose-600">{c.name.charAt(0)}</div>
              <span className="flex-1 font-medium">{c.name}</span>
              <span className="text-right text-xs text-slate-500">{c.days_absent}d absent · {c.visits} visits<br /><b className="text-slate-700">{inr(c.lifetime_paise)}</b></span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
