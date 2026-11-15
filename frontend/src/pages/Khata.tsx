import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, BookOpen, CheckCircle2, ListChecks, Wallet } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import ActionCard from "../components/ActionCard";
import { Badge, Button, Card, ChartTip, Empty, ErrorState, PageHeader, Spinner, Stat, Title } from "../components/ui";
import { compactInr, inr } from "../lib";

const BUCKETS = [
  { name: "0–7 days", min: 0, max: 7, color: "#10B981" },
  { name: "8–14 days", min: 8, max: 14, color: "#F59E0B" },
  { name: "15–21 days", min: 15, max: 21, color: "#F97316" },
  { name: "22+ days", min: 22, max: 9999, color: "#F43F5E" },
];

export default function Khata() {
  const qc = useQueryClient();
  const k = useQuery({ queryKey: ["khata"], queryFn: api.khata });
  const acts = useQuery({ queryKey: ["actions"], queryFn: api.actions });
  const [f, setF] = useState({ customer_name: "", phone: "", amount_rupees: "", note: "" });
  const add = useMutation({
    mutationFn: () => api.addKhata({ ...f, amount_rupees: Number(f.amount_rupees) }),
    onSuccess: () => { setF({ customer_name: "", phone: "", amount_rupees: "", note: "" }); void qc.invalidateQueries({ queryKey: ["khata"] }); void qc.invalidateQueries({ queryKey: ["dashboard"] }); },
  });
  const open = k.data?.open;
  const aging = useMemo(
    () => BUCKETS.map((b) => ({ ...b, amount: (open ?? []).filter((e) => e.days_pending >= b.min && e.days_pending <= b.max).reduce((a, e) => a + e.amount_paise / 100, 0) })),
    [open],
  );
  if (k.isLoading) return <Spinner />;
  if (k.error) return <ErrorState error={k.error} retry={() => k.refetch()} />;
  const d = k.data!;
  const khataActions = acts.data?.filter((a) => a.kind === "khata_reminders") ?? [];
  const split = [
    { name: "Overdue", value: d.summary.overdue_total_paise / 100, color: "#F43F5E" },
    { name: "Not yet due", value: Math.max(0, (d.summary.open_total_paise - d.summary.overdue_total_paise) / 100), color: "#F59E0B" },
    { name: "Recovered", value: d.summary.recovered_total_paise / 100, color: "#10B981" },
  ];
  return (
    <div className="space-y-5">
      <PageHeader icon={BookOpen} title="Udhaar (Khata)" sub="Tracks who owes you money and sends polite reminders with a Paytm payment link." right={<Badge tone="blue">Khata Agent</Badge>} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={Wallet} label="Total outstanding" value={inr(d.summary.open_total_paise)} tone="warn" />
        <Stat icon={AlertCircle} label="Overdue (14+ days)" value={inr(d.summary.overdue_total_paise)} tone="bad" hint={`${d.summary.overdue_count} customers`} />
        <Stat icon={ListChecks} label="Open entries" value={String(d.summary.open_count)} tone="neutral" />
        <Stat icon={CheckCircle2} label="Recovered" value={inr(d.summary.recovered_total_paise)} tone="good" />
      </div>
      {khataActions.map((a) => <ActionCard key={a.id} action={a} />)}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <Title sub="How old your outstanding udhaar is. The older it gets, the harder it is to recover.">Ageing of outstanding amounts</Title>
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={aging} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#64748b" }} tickFormatter={(v: number) => compactInr(v)} width={52} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTip money />} cursor={{ fill: "#f1f5f9" }} />
                <Bar dataKey="amount" name="Outstanding" radius={[8, 8, 0, 0]}>{aging.map((b) => <Cell key={b.name} fill={b.color} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <Title sub="Overdue vs pending vs recovered">Udhaar health</Title>
          <div className="h-40">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={split} dataKey="value" nameKey="name" innerRadius={42} outerRadius={64} paddingAngle={3} stroke="none">{split.map((s) => <Cell key={s.name} fill={s.color} />)}</Pie>
                <Tooltip content={<ChartTip money />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="space-y-1 text-sm">
            {split.map((s) => <li key={s.name} className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} /><span className="flex-1 text-slate-600">{s.name}</span><b>{compactInr(s.value)}</b></li>)}
          </ul>
        </Card>
      </div>
      <Card>
        <Title sub="Overdue customers are highlighted. Munim proposes reminders with a Paytm payment link.">Udhaar ledger</Title>
        {d.open.length === 0 ? <Empty>No pending udhaar. 🎉</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs uppercase tracking-wider text-slate-500"><th className="py-2">Customer</th><th>Note</th><th>Pending</th><th className="text-right">Amount</th></tr></thead>
              <tbody>
                {d.open.map((e) => (
                  <tr key={e.khata_id} className={`border-t border-slate-100 ${e.overdue ? "bg-rose-50/40" : ""}`}>
                    <td className="py-2.5"><div className="flex items-center gap-2.5"><div className="grid h-8 w-8 place-items-center rounded-full bg-slate-100 text-xs font-bold text-slate-600">{e.name.charAt(0)}</div><span className="font-medium">{e.name}</span></div></td>
                    <td className="text-slate-500">{e.note}</td>
                    <td>{e.overdue ? <Badge tone="red">{e.days_pending} days overdue</Badge> : <Badge>{e.days_pending} days</Badge>}</td>
                    <td className="text-right font-semibold">{inr(e.amount_paise)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <Card>
        <Title sub="Records a new udhaar so Munim can follow it up for you.">Add udhaar entry</Title>
        <form className="grid gap-3 md:grid-cols-5" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
          {([
            ["customer_name", "Customer name", "text"], ["phone", "Mobile (10 digits)", "text"], ["amount_rupees", "Amount ₹", "number"], ["note", "Note", "text"],
          ] as const).map(([key, ph, type]) => (
            <input key={key} required={key !== "note"} type={type} min={type === "number" ? 1 : undefined} pattern={key === "phone" ? "[6-9][0-9]{9}" : undefined}
              placeholder={ph} aria-label={ph} value={f[key]} onChange={(e) => setF({ ...f, [key]: e.target.value })}
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none focus:border-paytm-blue focus:bg-white focus:ring-4 focus:ring-sky-100" />
          ))}
          <Button type="submit" busy={add.isPending}>Add</Button>
        </form>
        {add.error && <div className="mt-2"><ErrorState error={add.error} /></div>}
      </Card>
    </div>
  );
}
