import { useQuery } from "@tanstack/react-query";
import { Clock, ShieldAlert, ShieldCheck, Siren } from "lucide-react";
import { api } from "../api";
import { Badge, Card, Empty, ErrorState, PageHeader, Spinner, Stat } from "../components/ui";
import { inr } from "../lib";

export default function Trust() {
  const q = useQuery({ queryKey: ["trust"], queryFn: api.trust });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  const alerts = q.data!.alerts;
  const high = alerts.filter((a) => a.severity === "high").length;
  const exposed = alerts.reduce((a, b) => a + b.amount_paise, 0);
  return (
    <div className="space-y-5">
      <PageHeader icon={ShieldAlert} title="Trust & safety" sub="Flags unusual payments using statistics, so you can check them. It never blocks or acts on its own." right={<Badge tone="blue">Trust Agent</Badge>} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={Siren} label="Alerts" value={String(alerts.length)} tone={alerts.length ? "warn" : "good"} />
        <Stat icon={ShieldAlert} label="High severity" value={String(high)} tone={high ? "bad" : "good"} />
        <Stat icon={Clock} label="Amount flagged" value={inr(exposed)} tone="neutral" />
        <Stat icon={ShieldCheck} label="Protection" value="Active" tone="good" hint="monitoring 24×7" />
      </div>
      {alerts.length === 0 && <Empty>No unusual payments found. 👍</Empty>}
      <div className="space-y-3">
        {alerts.map((a) => (
          <Card key={`${a.type}-${a.sale_id}`} className={`flex items-start gap-4 border-l-4 ${a.severity === "high" ? "border-l-rose-500" : "border-l-amber-400"}`}>
            <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-2xl ${a.severity === "high" ? "bg-rose-50 text-rose-600" : "bg-amber-50 text-amber-600"}`}><ShieldAlert className="h-5 w-5" /></div>
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xl font-bold text-slate-900">{inr(a.amount_paise)}</span>
                <Badge tone={a.severity === "high" ? "red" : "amber"}>{a.severity}</Badge>
                <Badge>{a.type.replace("_", " ")}</Badge>
                <span className="ml-auto text-xs text-slate-500">{new Date(a.at).toLocaleString("en-IN")}</span>
              </div>
              <p className="mt-1.5 text-sm text-slate-600">{a.reason}</p>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
