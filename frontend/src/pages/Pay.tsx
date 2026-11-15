import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { Button, ErrorState, Spinner } from "../components/ui";
import { inr } from "../lib";

/** Public mock of a Paytm payment page (customer opens this from the WhatsApp reminder). */
export default function Pay() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["pay", id], queryFn: () => api.payInfo(id) });
  const pay = useMutation({ mutationFn: () => api.pay(id), onSuccess: (d) => qc.setQueryData(["pay", id], d) });
  const d = q.data;
  return (
    <div className="grid min-h-screen place-items-center bg-sky-50 p-5">
      <div className="w-full max-w-sm overflow-hidden rounded-3xl bg-white shadow-xl">
        <div className="bg-paytm-navy p-5 text-white">
          <div className="text-xl font-bold">Pay<span className="text-paytm-blue">tm</span></div>
          <div className="text-xs text-sky-200">Secure payment (demo)</div>
        </div>
        <div className="p-6">
          {q.isLoading && <Spinner />}
          {q.error && <ErrorState error={q.error} />}
          {d && d.status === "paid" ? (
            <div className="space-y-2 text-center">
              <CheckCircle2 className="mx-auto h-16 w-16 text-emerald-500" />
              <div className="text-xl font-bold">Payment successful</div>
              <div className="text-3xl font-bold">{inr(d.amount_paise)}</div>
              <p className="text-slate-500">Paid to {d.merchant_name}. Thank you, {d.customer_name.split(" ")[0]}!</p>
            </div>
          ) : d && (
            <div className="space-y-4">
              <div><div className="text-sm text-slate-500">Paying</div><div className="text-lg font-semibold">{d.merchant_name}</div></div>
              <div className="text-4xl font-bold text-paytm-navy">{inr(d.amount_paise)}</div>
              <p className="text-sm text-slate-500">Udhaar for {d.customer_name} · {d.note}</p>
              <Button className="w-full py-3 text-base" busy={pay.isPending} onClick={() => pay.mutate()}>Pay {inr(d.amount_paise)} with UPI</Button>
              {pay.error && <ErrorState error={pay.error} />}
              <p className="text-center text-[11px] text-slate-400">Demo payment page. No real money moves. Production uses Paytm Payment Gateway.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
