import { useQuery } from "@tanstack/react-query";
import { BarChart3, CalendarDays, Clock, IndianRupee, Lightbulb, Receipt, TrendingDown, TrendingUp, Trophy, Users } from "lucide-react";
import { useMemo } from "react";
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { Badge, Card, ChartTip, ErrorState, PageHeader, Spinner, Stat, Title } from "../components/ui";
import { CHART, compactInr, inr } from "../lib";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const hourLabel = (h: number): string => `${h % 12 === 0 ? 12 : h % 12}${h < 12 ? "am" : "pm"}`;
const axis = { fontSize: 11, fill: "#64748b" };
const grid = <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />;

function Insight({ icon: Icon, children }: { icon: typeof Lightbulb; children: React.ReactNode }) {
  return (
    <div className="fade-up flex items-start gap-3 rounded-2xl border border-sky-100 bg-gradient-to-br from-sky-50 to-white p-3.5">
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-white text-paytm-blue shadow-sm ring-1 ring-sky-100"><Icon className="h-4 w-4" /></div>
      <p className="text-sm leading-snug text-slate-700">{children}</p>
    </div>
  );
}

export default function Insights() {
  const q = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const d = q.data;

  const m = useMemo(() => {
    if (!d || d.daily.length === 0) return null;
    const days = d.daily.map((x, i, arr) => {
      const win = arr.slice(Math.max(0, i - 6), i + 1);
      return {
        date: x.date, label: new Date(`${x.date}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" }),
        sales: x.sales_paise / 100, txns: x.txns, ma7: Math.round(win.reduce((a, b) => a + b.sales_paise, 0) / win.length / 100),
        dow: new Date(`${x.date}T00:00:00`).getDay(),
      };
    });
    const total = days.reduce((a, b) => a + b.sales, 0);
    const txns = days.reduce((a, b) => a + b.txns, 0);
    const avg = total / days.length;
    const best = days.reduce((a, b) => (b.sales > a.sales ? b : a));
    const last7 = days.slice(-7).reduce((a, b) => a + b.sales, 0);
    const prev7 = days.slice(-14, -7).reduce((a, b) => a + b.sales, 0);
    const wow = prev7 > 0 ? ((last7 - prev7) / prev7) * 100 : null;
    const dow = DAYS.map((name, i) => {
      const xs = days.filter((x) => x.dow === i);
      return { name, avg: xs.length ? Math.round(xs.reduce((a, b) => a + b.sales, 0) / xs.length) : 0 };
    });
    const bestDow = dow.reduce((a, b) => (b.avg > a.avg ? b : a));
    const hours = d.peak_hours.map((h) => ({ hour: hourLabel(h.hour), h: h.hour, txns: h.txns, sales: h.sales_paise / 100 }));
    const peak = hours.length ? hours.reduce((a, b) => (b.txns > a.txns ? b : a)) : null;
    const maxTx = Math.max(1, ...hours.map((x) => x.txns));
    const catTotal = d.category_mix.reduce((a, b) => a + b.revenue_paise, 0);
    const cats = d.category_mix.map((c) => ({ name: c.category, value: c.revenue_paise / 100, pct: catTotal ? (c.revenue_paise / catTotal) * 100 : 0 }));
    const products = d.top_products.slice(0, 8).map((p) => ({
      name: p.product.length > 16 ? `${p.product.slice(0, 15)}…` : p.product, full: p.product,
      revenue: p.revenue_paise / 100, profit: p.profit_paise / 100, margin: p.revenue_paise ? (p.profit_paise / p.revenue_paise) * 100 : 0,
    }));
    return { days, total, txns, avg, best, wow, dow, bestDow, hours, peak, maxTx, cats, catTotal, products, ticket: txns ? total / txns : 0, last7 };
  }, [d]);

  if (q.isLoading) return <Spinner label="Crunching your numbers" />;
  if (q.error) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  if (!d || !m) return <ErrorState error={new Error("No sales data yet")} />;

  const up = (m.wow ?? 0) >= 0;
  const topCat = m.cats[0];
  const topProd = m.products[0];
  const peerUp = d.peer.pct_vs_peers >= 0;
  const peerData = [
    { name: "You", v: d.peer.own_daily_avg_paise / 100 },
    { name: "Peer median", v: d.peer.peer_median_daily_paise / 100 },
  ];

  return (
    <div className="space-y-5">
      <PageHeader icon={BarChart3} title="Business insights" sub="Last 30 days of Paytm UPI sales. Every number is computed from your transactions, never guessed by AI."
        right={<Badge tone="blue">Insights Agent</Badge>} />

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {m.wow !== null && (
          <Insight icon={up ? TrendingUp : TrendingDown}>
            Sales are <b className={up ? "text-emerald-600" : "text-rose-600"}>{up ? "up" : "down"} {Math.abs(m.wow).toFixed(1)}%</b> this week ({compactInr(m.last7)}) compared with the week before.
          </Insight>
        )}
        <Insight icon={CalendarDays}><b>{m.bestDow.name}</b> is your strongest weekday, averaging <b>{compactInr(m.bestDow.avg)}</b> a day.</Insight>
        {m.peak && <Insight icon={Clock}>Customers pay most around <b>{m.peak.hour}</b> ({m.peak.txns} payments). Keep stock and staff ready then.</Insight>}
        {topCat && topProd && <Insight icon={Trophy}><b>{topCat.name}</b> brings {topCat.pct.toFixed(0)}% of revenue; <b>{topProd.full}</b> earns you the most profit.</Insight>}
      </div>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-5">
        <Stat icon={IndianRupee} tone="brand" label="30-day revenue" value={compactInr(m.total)} spark={m.days.map((x) => x.sales)} />
        <Stat icon={BarChart3} tone="neutral" label="Average per day" value={compactInr(m.avg)} hint={`${Math.round(m.txns / m.days.length)} payments/day`} />
        <Stat icon={Receipt} tone="neutral" label="Avg ticket size" value={`₹${Math.round(m.ticket)}`} hint="per payment" spark={m.days.map((x) => (x.txns ? x.sales / x.txns : 0))} />
        <Stat icon={Trophy} tone="good" label="Best day" value={compactInr(m.best.sales)} hint={m.best.label} />
        <Stat icon={Users} tone={peerUp ? "good" : "bad"} label="Vs similar stores" value={`${peerUp ? "+" : ""}${d.peer.pct_vs_peers}%`} hint={peerUp ? "ahead of peers" : "behind peers"} />
      </div>

      <Card>
        <Title sub="Daily revenue with a 7-day moving average to show the real trend" right={<Badge tone="blue">30 days</Badge>}>Sales trend</Title>
        <div className="h-72">
          <ResponsiveContainer>
            <ComposedChart data={m.days} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="ins-sales" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#00BAF2" stopOpacity={0.45} /><stop offset="100%" stopColor="#00BAF2" stopOpacity={0} /></linearGradient>
              </defs>
              {grid}
              <XAxis dataKey="label" tick={axis} interval={3} tickLine={false} axisLine={false} />
              <YAxis tick={axis} tickFormatter={(v: number) => compactInr(v)} width={52} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTip money />} />
              <ReferenceLine y={m.avg} stroke="#94a3b8" strokeDasharray="4 4" label={{ value: "avg", fontSize: 10, fill: "#94a3b8", position: "right" }} />
              <Area type="monotone" dataKey="sales" name="Daily sales" stroke="#00BAF2" strokeWidth={2} fill="url(#ins-sales)" />
              <Line type="monotone" dataKey="ma7" name="7-day average" stroke="#002E6E" strokeWidth={2.5} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <Title sub="Average revenue by weekday. The best day is highlighted.">Weekday pattern</Title>
          <div className="h-60">
            <ResponsiveContainer>
              <BarChart data={m.dow} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
                {grid}
                <XAxis dataKey="name" tick={axis} tickLine={false} axisLine={false} />
                <YAxis tick={axis} tickFormatter={(v: number) => compactInr(v)} width={52} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTip money />} cursor={{ fill: "#f1f5f9" }} />
                <Bar dataKey="avg" name="Avg sales" radius={[8, 8, 0, 0]}>
                  {m.dow.map((x) => <Cell key={x.name} fill={x.name === m.bestDow.name ? "#00BAF2" : "#BFE9F8"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <Title sub="When customers pay, last 14 days (IST). Darker means busier.">Peak hours</Title>
          <div className="h-60">
            <ResponsiveContainer>
              <BarChart data={m.hours} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
                {grid}
                <XAxis dataKey="hour" tick={axis} tickLine={false} axisLine={false} interval={1} />
                <YAxis tick={axis} width={34} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTip />} cursor={{ fill: "#f1f5f9" }} />
                <Bar dataKey="txns" name="Payments" radius={[6, 6, 0, 0]}>
                  {m.hours.map((x) => <Cell key={x.h} fill={`rgba(0,46,110,${0.18 + 0.82 * (x.txns / m.maxTx)})`} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <Title sub="Number of UPI payments received each day">Payments per day</Title>
          <div className="h-60">
            <ResponsiveContainer>
              <BarChart data={m.days} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
                {grid}
                <XAxis dataKey="label" tick={axis} interval={4} tickLine={false} axisLine={false} />
                <YAxis tick={axis} width={34} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTip />} cursor={{ fill: "#f1f5f9" }} />
                <Bar dataKey="txns" name="Payments" fill="#7C5CFC" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <Title sub="Share of revenue by product category">Category mix</Title>
          <div className="flex flex-col items-center gap-4 sm:flex-row">
            <div className="relative h-52 w-52 shrink-0">
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={m.cats} dataKey="value" nameKey="name" innerRadius={62} outerRadius={90} paddingAngle={2} stroke="none">
                    {m.cats.map((_, i) => <Cell key={i} fill={CHART[i % CHART.length]} />)}
                  </Pie>
                  <Tooltip content={<ChartTip money />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
                <div><div className="text-xl font-bold text-paytm-navy">{compactInr(m.catTotal / 100)}</div><div className="text-[11px] text-slate-500">revenue</div></div>
              </div>
            </div>
            <ul className="w-full space-y-1.5 text-sm">
              {m.cats.map((c, i) => (
                <li key={c.name} className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: CHART[i % CHART.length] }} />
                  <span className="flex-1 truncate text-slate-700">{c.name}</span>
                  <span className="font-semibold text-slate-900">{c.pct.toFixed(0)}%</span>
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <Title sub="Revenue vs profit for your top products, ranked by profit">Best products</Title>
          <div style={{ height: Math.max(380, m.products.length * 52) }}>
            <ResponsiveContainer>
              <BarChart data={m.products} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                <XAxis type="number" tick={axis} tickFormatter={(v: number) => compactInr(v)} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" tick={{ ...axis, fill: "#334155" }} width={108} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTip money />} cursor={{ fill: "#f1f5f9" }} />
                <Bar dataKey="revenue" name="Revenue" fill="#BFE9F8" radius={[0, 6, 6, 0]} barSize={13} />
                <Bar dataKey="profit" name="Profit" fill="#10B981" radius={[0, 6, 6, 0]} barSize={13} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-[#BFE9F8]" /> Revenue</span>
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-emerald-500" /> Profit</span>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <Title sub="Profit as a share of revenue">Margin by product</Title>
            <ul className="space-y-2.5">
              {[...m.products].sort((a, b) => b.margin - a.margin).slice(0, 6).map((p) => (
                <li key={p.full}>
                  <div className="mb-1 flex justify-between text-xs"><span className="truncate font-medium text-slate-700">{p.full}</span><span className="font-semibold text-emerald-700">{p.margin.toFixed(0)}%</span></div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-emerald-600" style={{ width: `${Math.min(100, p.margin * 2.5)}%` }} /></div>
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <Title sub="Average daily sales vs similar kirana stores">Peer benchmark</Title>
            <div className="flex items-baseline gap-2">
              <span className={`text-3xl font-bold ${peerUp ? "text-emerald-600" : "text-rose-600"}`}>{peerUp ? "+" : ""}{d.peer.pct_vs_peers}%</span>
              <span className="text-sm text-slate-500">{peerUp ? "ahead" : "behind"}</span>
            </div>
            <div className="mt-2 h-24">
              <ResponsiveContainer>
                <BarChart data={peerData} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="name" tick={axis} width={80} tickLine={false} axisLine={false} />
                  <Tooltip content={<ChartTip money />} cursor={false} />
                  <Bar dataKey="v" name="Avg/day" radius={[0, 8, 8, 0]} barSize={18}>
                    <Cell fill="#00BAF2" /><Cell fill="#CBD5E1" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-xs text-slate-500">You {inr(d.peer.own_daily_avg_paise)}/day · peers {inr(d.peer.peer_median_daily_paise)}/day</p>
            <div className="mt-2"><Badge>Synthetic benchmark for demo</Badge></div>
          </Card>
        </div>
      </div>
    </div>
  );
}
