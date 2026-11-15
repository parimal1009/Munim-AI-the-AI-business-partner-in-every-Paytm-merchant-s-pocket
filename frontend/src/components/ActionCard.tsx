import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink, ShieldCheck, X } from "lucide-react";
import { Link } from "react-router-dom";
import { api, type ActionItem } from "../api";
import { Badge, Button, Card, ErrorState } from "./ui";

const KIND: Record<string, { label: string; tone: "amber" | "blue" | "green" }> = {
  khata_reminders: { label: "Udhaar", tone: "amber" },
  reorder: { label: "Stock", tone: "blue" },
  campaign: { label: "Growth", tone: "green" },
  clearance: { label: "Expiry", tone: "amber" },
};

type Sent = { name: string; whatsapp_url?: string; pay_url?: string };

function Result({ a }: { a: ActionItem }) {
  const r = a.result as Record<string, unknown> | null;
  if (!r) return null;
  const sent = (r.sent as Sent[] | undefined) ?? [];
  return (
    <div className="mt-3 space-y-2 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">
      <div className="flex items-center gap-2 font-semibold"><Check className="h-4 w-4" /> Done</div>
      {r.kind === "khata_reminders" && (
        <>
          <p>{sent.length} reminders sent with Paytm payment links.</p>
          <div className="flex flex-wrap gap-2">
            {sent.map((s) => s.whatsapp_url && (
              <a key={s.name} href={s.whatsapp_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-lg bg-white px-2 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
                <ExternalLink className="h-3 w-3" /> WhatsApp {s.name.split(" ")[0]}
              </a>
            ))}
          </div>
          <Link to="/phone" className="font-semibold underline">See messages on the customer phone →</Link>
        </>
      )}
      {r.kind === "reorder" && <p>Purchase order #{String(r.purchase_order_id)} sent to {String(r.distributor)}.</p>}
      {r.kind === "clearance" && (
        <p>Clearance prices are live on {(r.items as unknown[] | undefined)?.length ?? 0} product(s) and the offer reached {String(r.customers)} customers. <Link to="/inventory" className="font-semibold underline">See Inventory →</Link></p>
      )}
      {r.kind === "campaign" && <p>Campaign live. {String(r.targets)} customers reached. <Link to="/growth" className="font-semibold underline">Track it →</Link></p>}
    </div>
  );
}

export default function ActionCard({ action }: { action: ActionItem }) {
  const qc = useQueryClient();
  const done = () => {
    ["dashboard", "khata", "inventory", "growth", "outcomes", "messages"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    // refetching these lists would unmount this card before it shows its result
    ["briefing", "actions"].forEach((k) => qc.invalidateQueries({ queryKey: [k], refetchType: "none" }));
  };
  const approve = useMutation({ mutationFn: () => api.approve(action.id), onSuccess: done });
  const reject = useMutation({ mutationFn: () => api.reject(action.id), onSuccess: done });
  const kind = KIND[action.kind] ?? { label: action.kind, tone: "blue" as const };
  const executed = approve.data ?? (action.status === "executed" ? action : null);
  return (
    <Card className="border-l-4 border-l-paytm-blue">
      <div className="mb-2 flex items-center gap-2">
        <Badge tone={kind.tone}>{kind.label}</Badge>
        <span className="flex items-center gap-1 text-xs text-slate-500"><ShieldCheck className="h-3.5 w-3.5" /> Needs your approval</span>
      </div>
      <h3 className="font-semibold">{action.title}</h3>
      <p className="mt-1 text-sm text-slate-600"><b>Because:</b> {action.reason}</p>
      {executed ? (
        <Result a={executed} />
      ) : (
        <div className="mt-3 flex gap-2">
          <Button variant="success" busy={approve.isPending} onClick={() => approve.mutate()}><Check className="h-4 w-4" /> Haan, approve</Button>
          <Button variant="danger" busy={reject.isPending} onClick={() => reject.mutate()}><X className="h-4 w-4" /> Skip</Button>
        </div>
      )}
      {(approve.error || reject.error) && <div className="mt-2"><ErrorState error={approve.error ?? reject.error} /></div>}
    </Card>
  );
}
