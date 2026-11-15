import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { Empty, ErrorState, Spinner } from "../components/ui";

/** Stand-in for WhatsApp: shows what customers/distributors would receive. */
export default function Phone() {
  const q = useQuery({ queryKey: ["messages"], queryFn: api.messages, refetchInterval: 4000 });
  const [sel, setSel] = useState<string | null>(null);
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  const threads = q.data!;
  const cur = threads.find((t) => t.phone === sel) ?? threads[0];
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-paytm-navy">Customer Phone (WhatsApp simulator)</h1>
        <p className="text-slate-600">What your customers and distributors receive after you approve. In production this is the WhatsApp Business API (see Roadmap).</p>
      </div>
      {threads.length === 0 ? <Empty>No messages yet. Approve a reminder or order on Home.</Empty> : (
        <div className="mx-auto grid max-w-3xl gap-4 md:grid-cols-[220px_1fr]">
          <div className="space-y-1">
            {threads.map((t) => (
              <button key={t.phone} onClick={() => setSel(t.phone)} className={`w-full rounded-xl border px-3 py-2 text-left text-sm ${cur?.phone === t.phone ? "border-paytm-blue bg-sky-50" : "bg-white"}`}>
                <div className="font-semibold">{t.name}</div><div className="text-xs text-slate-500">+91 {t.phone}</div>
              </button>
            ))}
          </div>
          {cur && (
            <div className="overflow-hidden rounded-[2rem] border-8 border-slate-800 bg-[#ECE5DD] shadow-xl">
              <div className="bg-[#075E54] px-4 py-3 text-white"><div className="font-semibold">{cur.name}</div><div className="text-xs opacity-80">via WhatsApp (simulated)</div></div>
              <div className="min-h-[320px] space-y-3 p-3">
                {cur.messages.map((m) => (
                  <div key={m.id} className="ml-auto max-w-[88%] rounded-xl rounded-tr-none bg-[#DCF8C6] p-3 text-sm shadow">
                    <p className="whitespace-pre-wrap break-words">{m.body}</p>
                    {m.payment_link_id && (
                      <a href={`/pay/${m.payment_link_id}`} target="_blank" rel="noreferrer"
                        className={`mt-2 block rounded-lg px-3 py-2 text-center font-semibold ${m.link_status === "paid" ? "bg-emerald-600 text-white" : "bg-paytm-blue text-white"}`}>
                        {m.link_status === "paid" ? "Paid ✓" : "Pay with Paytm"}
                      </a>
                    )}
                    <div className="mt-1 text-right text-[10px] text-slate-500">{new Date(m.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} ✓✓</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
