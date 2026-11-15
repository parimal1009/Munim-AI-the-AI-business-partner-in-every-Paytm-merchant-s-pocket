import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, CheckCircle2, Eye, Package, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import ActionCard from "../components/ActionCard";
import { Badge, Card, ChartTip, ErrorState, PageHeader, Spinner, Stat, Title } from "../components/ui";
import { inr } from "../lib";

const tone = (c: number | null): "slate" | "red" | "amber" | "green" => (c === null ? "slate" : c <= 3.5 ? "red" : c <= 6 ? "amber" : "green");
const sevTone = (s: string): "red" | "amber" | "blue" => (s === "expired" || s === "critical" ? "red" : s === "soon" ? "amber" : "blue");
const color = (c: number): string => (c <= 3.5 ? "#F43F5E" : c <= 6 ? "#F59E0B" : "#10B981");

export default function Inventory() {
  const q = useQuery({ queryKey: ["inventory"], queryFn: api.inventory });
  const acts = useQuery({ queryKey: ["actions"], queryFn: api.actions });
  const [filter, setFilter] = useState("");
  const rows = q.data?.products;
  const chart = useMemo(
    () => (rows ?? []).filter((r) => r.days_of_cover !== null).map((r) => ({ name: r.name.length > 18 ? `${r.name.slice(0, 17)}…` : r.name, cover: r.days_of_cover as number }))
      .sort((a, b) => a.cover - b.cover).slice(0, 12),
    [rows],
  );
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  const all = rows ?? [];
  const critical = all.filter((r) => r.days_of_cover !== null && r.days_of_cover <= 3.5).length;
  const watch = all.filter((r) => r.days_of_cover !== null && r.days_of_cover > 3.5 && r.days_of_cover <= 6).length;
  const healthy = all.filter((r) => r.days_of_cover !== null && r.days_of_cover > 6).length;
  const reorderActions = acts.data?.filter((a) => a.kind === "reorder" || a.kind === "clearance") ?? [];
  const expiring = q.data?.expiring ?? [];
  const expiringWeek = expiring.filter((e) => e.days_left <= 7).length;
  const shown = all.filter((r) => r.name.toLowerCase().includes(filter.toLowerCase()) || r.category.toLowerCase().includes(filter.toLowerCase()));
  return (
    <div className="space-y-5">
      <PageHeader icon={Package} title="Inventory" sub="Forecasts demand from your sales and drafts distributor orders for your approval." right={<Badge tone="blue">Inventory Agent</Badge>} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Stat icon={Package} label="Products tracked" value={String(all.length)} tone="brand" />
        <Stat icon={AlertTriangle} label="Critical (≤3.5 days)" value={String(critical)} tone={critical ? "bad" : "good"} hint={critical ? "reorder now" : "none"} />
        <Stat icon={Eye} label="Watch (≤6 days)" value={String(watch)} tone={watch ? "warn" : "good"} />
        <Stat icon={CheckCircle2} label="Healthy" value={String(healthy)} tone="good" />
        <Stat icon={CalendarClock} label="Expiring (≤7 days)" value={String(expiringWeek)} tone={expiringWeek ? "bad" : "good"} hint={expiringWeek ? "act now" : "none"} />
      </div>
      {reorderActions.map((a) => <ActionCard key={a.id} action={a} />)}
      {expiring.length > 0 && (
        <Card>
          <Title sub="Batches that will probably not sell out before they expire. Discounts never go below your cost."
            right={<Badge tone="amber">{expiring.length} near expiry</Badge>}>Expiring soon</Title>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs uppercase tracking-wider text-slate-500"><th className="py-2">Product</th><th>Expires</th><th>In stock</th><th>Likely unsold</th><th>At risk (cost)</th><th>Discount</th></tr></thead>
              <tbody>
                {expiring.map((e) => (
                  <tr key={e.product_id} className="border-t border-slate-100">
                    <td className="py-2.5 font-medium text-slate-800">{e.name}</td>
                    <td><Badge tone={sevTone(e.severity)}>{e.days_left < 0 ? "expired" : e.days_left === 0 ? "today" : `${e.days_left} day${e.days_left === 1 ? "" : "s"}`}</Badge></td>
                    <td>{e.stock_qty} <span className="text-xs text-slate-400">{e.unit}</span></td>
                    <td>{e.units_at_risk}</td>
                    <td>{inr(e.value_at_risk_paise)}</td>
                    <td>
                      {e.clearance_pct ? (
                        <span className="inline-flex items-center gap-2"><Badge tone="green">{e.clearance_pct}% off live</Badge><span className="text-xs text-slate-400 line-through">{inr(e.price_paise)}</span><b>{inr(e.selling_price_paise)}</b></span>
                      ) : e.days_left < 0 ? <Badge tone="red">remove from shelf</Badge>
                        : e.suggested_discount_pct ? <Badge tone="amber">suggest {e.suggested_discount_pct}% off</Badge>
                        : <span className="text-xs text-slate-400">{e.units_at_risk ? "margin too thin: sell first or return" : "will sell in time"}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      <Card>
        <Title sub="Products closest to running out. Red bars are below 3.5 days of cover." right={<Badge tone="red">Lowest first</Badge>}>Days of stock left</Title>
        <div style={{ height: Math.max(240, chart.length * 30) }}>
          <ResponsiveContainer>
            <BarChart data={chart} layout="vertical" margin={{ top: 0, right: 24, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} unit="d" />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#334155" }} width={120} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTip />} cursor={{ fill: "#f1f5f9" }} />
              <ReferenceLine x={3.5} stroke="#F43F5E" strokeDasharray="4 4" />
              <Bar dataKey="cover" name="Days of cover" radius={[0, 8, 8, 0]} barSize={16}>
                {chart.map((c) => <Cell key={c.name} fill={color(c.cover)} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card>
        <Title sub="Days of cover = stock ÷ average daily units sold over the last 14 days"
          right={
            <label className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Search products" aria-label="Search products"
                className="w-44 rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm outline-none focus:border-paytm-blue focus:bg-white" />
            </label>
          }>Stock health</Title>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs uppercase tracking-wider text-slate-500"><th className="py-2">Product</th><th>Category</th><th>In stock</th><th>Sells/day</th><th>Price</th><th>Cover</th></tr></thead>
            <tbody>
              {shown.map((r) => {
                const c = r.days_of_cover;
                return (
                  <tr key={r.product_id} className="border-t border-slate-100 transition hover:bg-slate-50">
                    <td className="py-2.5 font-medium text-slate-800">{r.name}</td><td className="text-slate-500">{r.category}</td>
                    <td>{r.stock_qty} <span className="text-xs text-slate-400">{r.unit}</span></td><td>{r.avg_daily_units}</td>
                    <td>{r.clearance_pct ? <span><span className="text-xs text-slate-400 line-through">{inr(r.price_paise)}</span> <b>{inr(r.selling_price_paise)}</b> <Badge tone="green">{r.clearance_pct}% off</Badge></span> : inr(r.price_paise)}</td>
                    <td><Badge tone={tone(c)}>{c === null ? "no sales" : `${c} days`}</Badge></td>
                  </tr>
                );
              })}
              {shown.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-slate-400">No products match.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
