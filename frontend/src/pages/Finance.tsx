import { useQuery } from "@tanstack/react-query";
import { CalendarClock, Landmark, Percent, ReceiptText, Wallet } from "lucide-react";
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, PolarAngleAxis, RadialBar, RadialBarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Badge, Card, ChartTip, ErrorState, PageHeader, Spinner, Stat, Title } from "../components/ui";
import { CHART, compactInr, inr } from "../lib";

export default function Finance() {
  const q = useQuery({ queryKey: ["finance"], queryFn: api.finance });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  const { forecast, loan, gst } = q.data!;
  const fc = forecast.map((f) => ({ day: new Date(f.date).toLocaleDateString("en-IN", { weekday: "short", day: "numeric" }), v: f.expected_paise / 100 }));
  const week = fc.reduce((a, b) => a + b.v, 0);
  const peak = fc.length ? fc.reduce((a, b) => (b.v > a.v ? b : a)) : null;
  const score = loan.stability_score ?? 0;
  const scoreColor = score >= 70 ? "#10B981" : score >= 45 ? "#F59E0B" : "#F43F5E";
  const slabs = gst.slabs.map((s) => ({ name: `${s.rate}% slab`, value: s.tax_paise / 100 }));
  return (
    <div className="space-y-5">
      <PageHeader icon={Wallet} title="Finance" sub="Cash-flow forecast, indicative loan eligibility and GST, all computed from your Paytm cash flow." right={<Badge tone="blue">Finance Agent</Badge>} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={CalendarClock} label="Expected next 7 days" value={compactInr(week)} tone="brand" spark={fc.map((f) => f.v)} />
        <Stat icon={CalendarClock} label="Strongest day ahead" value={peak ? compactInr(peak.v) : "—"} hint={peak?.day} tone="good" />
        <Stat icon={Landmark} label="Indicative loan limit" value={loan.eligible ? inr(loan.indicative_limit_paise ?? 0) : "Not yet"} tone={loan.eligible ? "good" : "warn"} hint={loan.eligible ? `${loan.indicative_tenure_months} months` : undefined} />
        <Stat icon={Percent} label={`GST (${gst.days} days)`} value={inr(gst.total_gst_paise)} tone="neutral" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <Title sub="Weekday-seasonal statistical forecast from the last 8 weeks">Cash-flow forecast, next 7 days</Title>
          <div className="h-64">
            <ResponsiveContainer>
              <AreaChart data={fc} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
                <defs><linearGradient id="fc" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7C5CFC" stopOpacity={0.45} /><stop offset="100%" stopColor="#7C5CFC" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#64748b" }} tickFormatter={(v: number) => compactInr(v)} width={52} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTip money />} />
                <Area type="monotone" dataKey="v" name="Expected" stroke="#7C5CFC" strokeWidth={2.5} fill="url(#fc)" dot={{ r: 3, fill: "#7C5CFC" }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <Title sub="Computed from your Paytm UPI cash flow">Loan eligibility</Title>
          {loan.eligible ? (
            <>
              <div className="relative mx-auto h-40 w-40">
                <ResponsiveContainer>
                  <RadialBarChart innerRadius="72%" outerRadius="100%" data={[{ v: score }]} startAngle={90} endAngle={-270}>
                    <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                    <RadialBar dataKey="v" cornerRadius={12} background={{ fill: "#f1f5f9" }}><Cell fill={scoreColor} /></RadialBar>
                  </RadialBarChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
                  <div><div className="text-3xl font-bold text-paytm-navy">{score}</div><div className="text-[11px] text-slate-500">income stability</div></div>
                </div>
              </div>
              <div className="mt-2 text-center">
                <Badge tone="green">Indicatively eligible</Badge>
                <div className="mt-1 text-3xl font-bold text-paytm-navy">{inr(loan.indicative_limit_paise ?? 0)}</div>
                <p className="text-sm text-slate-600">for {loan.indicative_tenure_months} months</p>
              </div>
              <p className="mt-2 text-center text-xs text-slate-500">{loan.note}</p>
            </>
          ) : <><Badge tone="amber">Not yet</Badge><p className="mt-2 text-slate-600">{loan.reason}</p></>}
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <Title sub="Tax collected by slab">GST split</Title>
          <div className="h-44">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={slabs} dataKey="value" nameKey="name" innerRadius={46} outerRadius={72} paddingAngle={3} stroke="none">{slabs.map((_, i) => <Cell key={i} fill={CHART[i % CHART.length]} />)}</Pie>
                <Tooltip content={<ChartTip money />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="space-y-1 text-sm">
            {slabs.map((s, i) => <li key={s.name} className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: CHART[i % CHART.length] }} /><span className="flex-1 text-slate-600">{s.name}</span><b>{compactInr(s.value)}</b></li>)}
          </ul>
        </Card>
        <Card className="lg:col-span-2">
          <Title sub={`Last ${gst.days} days. Prices are GST-inclusive; tax split per slab.`} right={<ReceiptText className="h-5 w-5 text-slate-300" />}>GST summary</Title>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs uppercase tracking-wider text-slate-500"><th className="py-2">Slab</th><th>Gross sales</th><th>Taxable value</th><th className="text-right">GST</th></tr></thead>
              <tbody>
                {gst.slabs.map((s) => (
                  <tr key={s.rate} className="border-t border-slate-100"><td className="py-2.5"><Badge tone="blue">{s.rate}%</Badge></td><td>{inr(s.gross_paise)}</td><td>{inr(s.taxable_paise)}</td><td className="text-right font-semibold">{inr(s.tax_paise)}</td></tr>
                ))}
                <tr className="border-t-2 border-slate-200 font-bold"><td className="py-2.5">Total</td><td /><td>{inr(gst.total_taxable_paise)}</td><td className="text-right">{inr(gst.total_gst_paise)}</td></tr>
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
